"""Testes do repositório em memória.

Testar o fake pode parecer redundante, mas ele codifica o CONTRATO do storage
real: uma trajetória sai ordenada no tempo, monótona, e recoletar o mesmo
instante não duplica (idempotência). Quando o SqliteRepository chegar, ele tem
que passar exatamente nestes mesmos testes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from breakout.types import Snapshot
from tests.fakes.repository import InMemoryTrajectoryRepository

pytestmark = pytest.mark.unit

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _snap(vid, hours, views):
    return Snapshot(video_id=vid, at=T0 + timedelta(hours=hours), views=views)


def test_roundtrip_e_ordena_por_tempo(repo: InMemoryTrajectoryRepository):
    # Insere fora de ordem de propósito.
    repo.save_snapshot(_snap("v", 2, 300))
    repo.save_snapshot(_snap("v", 0, 100))
    repo.save_snapshot(_snap("v", 1, 200))
    traj = repo.get_trajectory("v")
    assert np.array_equal(traj.t_hours, np.array([0.0, 1.0, 2.0]))
    assert np.array_equal(traj.views, np.array([100, 200, 300]))


def test_snapshot_e_idempotente_por_instante(repo: InMemoryTrajectoryRepository):
    repo.save_snapshot(_snap("v", 0, 100))
    repo.save_snapshot(_snap("v", 0, 999))   # mesmo instante -> sobrescreve
    traj = repo.get_trajectory("v")
    assert traj.views.size == 1
    assert traj.views[0] == 999


def test_video_ids_lista_os_coletados(repo: InMemoryTrajectoryRepository):
    repo.save_snapshot(_snap("a", 0, 1))
    repo.save_snapshot(_snap("b", 0, 1))
    assert set(repo.video_ids()) == {"a", "b"}


def test_get_trajectory_inexistente_levanta(repo: InMemoryTrajectoryRepository):
    with pytest.raises(KeyError):
        repo.get_trajectory("nao_existe")
