"""Testes do dashboard — Parte 1 do plano `dashboard-multimodal-e-coleta.md`
(Fase 7): mostrar thumbnail/transcrição no modo "Dados reais", opt-in via
checkbox — mesmo motivo de `with_multimodal=False` ser o padrão em
`features.py`: baixar a thumbnail a cada rerun do Streamlit seria caro se
ligado sozinho.

Usa `streamlit.testing.v1.AppTest` contra um SQLite temporário semeado à mão
(mesmo padrão dos smoke tests manuais já usados a sessão inteira, agora
formalizado como teste de verdade), com `respx` mockando o download da
thumbnail (Princípio 3: mockar só a fronteira externa real).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from breakout.settings import Settings
from breakout.storage.connection import make_connection
from breakout.storage.sql_repository import SqlTrajectoryRepository
from breakout.types import Snapshot, VideoMetadata

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("local_sqlite_env")]

DASHBOARD_PATH = str(Path(__file__).resolve().parents[2] / "src" / "breakout" / "dashboard.py")
THUMB_URL = "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def video_com_thumbnail_e_transcricao(local_sqlite_env, tmp_path):
    """Semeia um vídeo com thumbnail_url + transcript no MESMO SQLite
    temporário que `local_sqlite_env` já configurou pro processo (mesmo
    LOCAL_DB_PATH, então o dashboard enxerga o que semeamos aqui). Depende
    explicitamente de `local_sqlite_env` pra garantir a ordem (env var e
    cache limpo ANTES de escrever no banco)."""
    settings = Settings(
        local_db_path=str(tmp_path / "dashboard_test.db"),
        turso_database_url="",
        turso_auth_token="",
    )
    conn = make_connection(settings)
    repo = SqlTrajectoryRepository(conn)
    repo.init_schema()
    repo.save_metadata(
        VideoMetadata(
            video_id="v1",
            channel_id="c1",
            title="Vídeo de teste",
            duration_s=30,
            published_at=T0,
            thumbnail_url=THUMB_URL,
            transcript="Oi pessoal, bem vindos ao vídeo de hoje!",
        )
    )
    repo.save_snapshot(Snapshot(video_id="v1", at=T0, views=100))
    repo.save_snapshot(Snapshot(video_id="v1", at=T0 + timedelta(hours=2), views=500))
    conn.commit()


def _open_on_real_data():
    at = AppTest.from_file(DASHBOARD_PATH)
    at.run(timeout=30)
    at.sidebar.radio[0].set_value("Dados reais").run(timeout=30)
    return at


def _multimodal_checkbox(at):
    # "multimoda" (não "multimodal") pega tanto o singular quanto o plural em
    # português ("multimodais") — "multimodal" sozinho NÃO é substring de
    # "multimodais" (o "l" vira "i" antes do "s"), o que já causou um
    # `StopIteration` enganoso aqui.
    return next(c for c in at.main.checkbox if "multimoda" in c.label.lower())


def test_checkbox_desligado_por_padrao_sem_rede(video_com_thumbnail_e_transcricao):
    # Sem respx.mock ativo: se o dashboard tentasse baixar a thumbnail aqui,
    # a chamada HTTP real quebraria o teste.
    at = _open_on_real_data()
    assert list(at.exception) == []
    assert _multimodal_checkbox(at).value is False


@respx.mock
def test_checkbox_ligado_mostra_features_e_transcricao(video_com_thumbnail_e_transcricao):
    respx.get(THUMB_URL).mock(return_value=httpx.Response(200, content=b"bytes-de-imagem-falsos"))

    at = _open_on_real_data()
    _multimodal_checkbox(at).set_value(True).run(timeout=30)
    assert list(at.exception) == []

    texts = [w.value for w in at.main.get("markdown")]
    assert any("Oi pessoal" in t for t in texts)


@respx.mock
def test_checkbox_ligado_com_download_falho_nao_quebra(video_com_thumbnail_e_transcricao):
    # extract_thumbnail_features nunca levanta (Fase 5) — confirma que o
    # dashboard também não quebra quando o download falha (404).
    respx.get(THUMB_URL).mock(return_value=httpx.Response(404))

    at = _open_on_real_data()
    _multimodal_checkbox(at).set_value(True).run(timeout=30)
    assert list(at.exception) == []
