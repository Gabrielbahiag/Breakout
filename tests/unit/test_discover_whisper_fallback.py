"""Testes de `cli.py::_run_discover` — fallback de transcrição via Whisper
(Fase 7, `planning/transcricao-whisper.md`).

Propriedade crítica a travar: legenda (grátis, sem download de mídia) é
SEMPRE a primeira tentativa; Whisper só roda quando não há legenda E o
fallback está habilitado. `youtube-transcript-api` (`[prod]`) e
`faster-whisper`/`yt-dlp` (`[whisper]`) não estão instalados neste ambiente
de teste (`[dev]` só) — isso é usado a favor do teste: em vez de importar os
módulos reais (o que quebraria com `ModuleNotFoundError` de verdade, já que
`transcript_api.py`/`whisper_transcribe.py` fazem `import
youtube_transcript_api`/`faster_whisper` no nível do módulo), injetamos
módulos FALSOS em `sys.modules` antes do import preguiçoso de
`_run_discover` acontecer. Isso também prova, de graça, que o import de
`whisper_transcribe` é condicional: se o código o importasse fora da hora
certa (sem termos injetado o fake), estouraria `ModuleNotFoundError` real.
"""
from __future__ import annotations

import sqlite3
import sys
import types
from datetime import datetime, timezone

import pytest

from breakout.cli import _run_discover
from breakout.settings import Settings
from breakout.storage.sql_repository import SqlTrajectoryRepository
from breakout.types import VideoMetadata
from tests.fakes.clock import ManualClock
from tests.fakes.youtube import FakeYouTubeClient

pytestmark = pytest.mark.unit

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeContainer:
    def __init__(self, yt, repo, conn, clock, settings):
        self._yt = yt
        self.repo = repo
        self.connection = conn
        self.clock = clock
        self.settings = settings

    def youtube(self):
        return self._yt


@pytest.fixture
def container():
    conn = sqlite3.connect(":memory:")
    repo = SqlTrajectoryRepository(conn)
    repo.init_schema()
    yt = FakeYouTubeClient()
    yt.set_series("v1", [10])
    yt.set_metadata(
        VideoMetadata(video_id="v1", channel_id="c1", title="t", duration_s=30, published_at=T0)
    )
    return _FakeContainer(yt, repo, conn, ManualClock(T0), Settings(whisper_fallback_enabled=False))


def _fake_transcript_api(monkeypatch, fetch_transcript_text):
    """Injeta um `breakout.collect.transcript_api` FALSO em `sys.modules` —
    o módulo real importa `youtube_transcript_api` ([prod]) no nível do
    módulo, que não está instalado no ambiente de teste ([dev] só)."""
    fake_module = types.ModuleType("breakout.collect.transcript_api")
    fake_module.fetch_transcript_text = fetch_transcript_text
    monkeypatch.setitem(sys.modules, "breakout.collect.transcript_api", fake_module)


def _fake_whisper_transcribe(monkeypatch, transcribe_via_whisper):
    fake_module = types.ModuleType("breakout.collect.whisper_transcribe")
    fake_module.transcribe_via_whisper = transcribe_via_whisper
    monkeypatch.setitem(sys.modules, "breakout.collect.whisper_transcribe", fake_module)


def _saved_metadata(container) -> VideoMetadata:
    return container.repo.list_metadata()[0]


def test_legenda_disponivel_nunca_aciona_whisper(container, monkeypatch):
    _fake_transcript_api(monkeypatch, lambda video_id: "texto da legenda")

    _run_discover(container, "query", 50)

    meta = _saved_metadata(container)
    assert meta.transcript == "texto da legenda"
    assert meta.transcript_source == "caption"


def test_sem_legenda_e_fallback_desligado_nao_importa_whisper(container, monkeypatch):
    _fake_transcript_api(monkeypatch, lambda video_id: None)
    assert container.settings.whisper_fallback_enabled is False

    _run_discover(container, "query", 50)  # não pode levantar ModuleNotFoundError

    meta = _saved_metadata(container)
    assert meta.transcript == ""
    assert meta.transcript_source == ""


def test_sem_legenda_e_fallback_ligado_usa_whisper(container, monkeypatch):
    _fake_transcript_api(monkeypatch, lambda video_id: None)
    container.settings = Settings(whisper_fallback_enabled=True)

    calls: list[str] = []
    _fake_whisper_transcribe(
        monkeypatch, lambda video_id: (calls.append(video_id) or "texto via whisper")
    )

    _run_discover(container, "query", 50)

    assert calls == ["v1"]
    meta = _saved_metadata(container)
    assert meta.transcript == "texto via whisper"
    assert meta.transcript_source == "whisper"


def test_sem_legenda_whisper_tambem_falha_source_fica_vazio(container, monkeypatch):
    _fake_transcript_api(monkeypatch, lambda video_id: None)
    container.settings = Settings(whisper_fallback_enabled=True)
    _fake_whisper_transcribe(monkeypatch, lambda video_id: None)

    _run_discover(container, "query", 50)

    meta = _saved_metadata(container)
    assert meta.transcript == ""
    assert meta.transcript_source == ""
