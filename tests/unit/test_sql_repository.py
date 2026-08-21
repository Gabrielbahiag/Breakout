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
from breakout.types import Snapshot
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


def test_honra_o_contrato(any_repo):
    assert isinstance(any_repo, TrajectoryRepository)


def test_roundtrip_ordena_por_tempo(any_repo):
    any_repo.save_snapshot(_snap("v", 2, 300))
    any_repo.save_snapshot(_snap("v", 0, 100))
    any_repo.save_snapshot(_snap("v", 1, 200))
    traj = any_repo.get_trajectory("v")
    assert np.array_equal(traj.t_hours, np.array([0.0, 1.0, 2.0]))
    assert np.array_equal(traj.views, np.array([100, 200, 300]))


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
