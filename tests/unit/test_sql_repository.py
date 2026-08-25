"""Contrato de storage rodado contra as DUAS implementações.

Este é o teste que prova que a troca dev↔Turso é segura: o repositório SQL (que
em produção fala com o Turso, aqui com um sqlite `:memory:`) passa exatamente nos
mesmos testes que o fake em memória. Se os dois honram o contrato, o composition
root pode escolher qualquer um sem que o resto do sistema perceba.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from breakout.contracts import TrajectoryRepository
from breakout.storage.sql_repository import SqlTrajectoryRepository
from breakout.types import Snapshot, VideoMetadata
from tests.fakes.repository import InMemoryTrajectoryRepository

pytestmark = pytest.mark.unit

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_inmemory():
    return InMemoryTrajectoryRepository()


def _make_sql():
    conn = sqlite3.connect(":memory:")
    repo = SqlTrajectoryRepository(conn)
    repo.init_schema()
    return repo


@pytest.fixture(params=[_make_inmemory, _make_sql], ids=["in_memory", "sql_sqlite"])
def any_repo(request):
    return request.param()


def _snap(vid, hours, views, likes=0, comments=0):
    return Snapshot(video_id=vid, at=T0 + timedelta(hours=hours), views=views, likes=likes, comments=comments)


def _meta(vid, title):
    return VideoMetadata(
        video_id=vid, channel_id="c", title=title, duration_s=30, published_at=T0,
    )


def test_honra_o_contrato(any_repo):
    assert isinstance(any_repo, TrajectoryRepository)


def test_roundtrip_ordena_por_tempo(any_repo):
    any_repo.save_snapshot(_snap("v", 2, 300))
    any_repo.save_snapshot(_snap("v", 0, 100))
    any_repo.save_snapshot(_snap("v", 1, 200))
    traj = any_repo.get_trajectory("v")
    assert np.array_equal(traj.t_hours, np.array([0.0, 1.0, 2.0]))
    assert np.array_equal(traj.views, np.array([100, 200, 300]))


def test_get_trajectory_absorve_queda_real_de_views(any_repo):
    # A API do YouTube às vezes CORRIGE a contagem pra baixo (remoção de
    # views fraudulentas/bot) — não é bug nosso, é a fonte de dados. O
    # snapshot bruto (300 em t=1) fica intocado; get_trajectory() precisa
    # devolver uma Trajectory válida (monótona) mesmo assim, sem levantar.
    any_repo.save_snapshot(_snap("v", 0, 100))
    any_repo.save_snapshot(_snap("v", 1, 300))
    any_repo.save_snapshot(_snap("v", 2, 250))  # caiu — a API corrigiu
    any_repo.save_snapshot(_snap("v", 3, 400))
    traj = any_repo.get_trajectory("v")
    assert np.array_equal(traj.views, np.array([100, 300, 300, 400]))
    snaps = any_repo.get_snapshots("v")
    assert [s.views for s in snaps] == [100, 300, 250, 400]  # snapshot bruto INTOCADO


def test_snapshot_idempotente_por_instante(any_repo):
    any_repo.save_snapshot(_snap("v", 0, 100))
    any_repo.save_snapshot(_snap("v", 0, 999))
    traj = any_repo.get_trajectory("v")
    assert traj.views.size == 1
    assert traj.views[0] == 999


def test_video_ids(any_repo):
    any_repo.save_snapshot(_snap("a", 0, 1))
    any_repo.save_snapshot(_snap("b", 0, 1))
    assert set(any_repo.video_ids()) == {"a", "b"}


def test_get_inexistente_levanta(any_repo):
    with pytest.raises(KeyError):
        any_repo.get_trajectory("nao_existe")


def test_get_snapshots_ordena_e_preserva_likes_comments(any_repo):
    any_repo.save_snapshot(_snap("v", 1, 200, likes=20, comments=2))
    any_repo.save_snapshot(_snap("v", 0, 100, likes=10, comments=1))
    snaps = any_repo.get_snapshots("v")
    assert [s.views for s in snaps] == [100, 200]
    assert [s.likes for s in snaps] == [10, 20]
    assert [s.comments for s in snaps] == [1, 2]
    assert snaps[0].at < snaps[1].at


def test_get_snapshots_inexistente_devolve_lista_vazia(any_repo):
    assert any_repo.get_snapshots("nao_existe") == []


def test_list_metadata_devolve_todos_os_metadados_salvos(any_repo):
    any_repo.save_metadata(_meta("a", "Título A"))
    any_repo.save_metadata(_meta("b", "Título B"))
    titles = {m.video_id: m.title for m in any_repo.list_metadata()}
    assert titles == {"a": "Título A", "b": "Título B"}


def test_list_metadata_vazio_quando_nao_ha_metadados(any_repo):
    assert any_repo.list_metadata() == []


def test_video_peak_views_devolve_o_maximo_por_video(any_repo):
    any_repo.save_snapshot(_snap("a", 0, 100))
    any_repo.save_snapshot(_snap("a", 1, 300))
    any_repo.save_snapshot(_snap("a", 2, 250))  # queda real (correção da API)
    any_repo.save_snapshot(_snap("b", 0, 999_999))
    assert any_repo.video_peak_views() == {"a": 300, "b": 999_999}


def test_video_peak_views_vazio_quando_nao_ha_snapshots(any_repo):
    assert any_repo.video_peak_views() == {}
