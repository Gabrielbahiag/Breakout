"""Testes das métricas do Motor A.

Aqui testamos a MÉTRICA em si (não a qualidade de nenhum detector) contra
exemplos montados à mão, onde a resposta certa é óbvia. É o tipo de teste que
tem que ser cristalino, porque todo o resto do Motor A vai depender dele.
"""
from __future__ import annotations

import numpy as np
import pytest

from breakout.engine_a.metrics import crossing_hours, lead_time_hours
from breakout.types import Detection, Trajectory

pytestmark = pytest.mark.unit


def _traj(views: list[int]) -> Trajectory:
    t = np.arange(len(views), dtype=float)
    return Trajectory("hand", t, np.array(views, dtype=np.int64))


def test_crossing_hours_encontra_primeiro_cruzamento():
    traj = _traj([0, 10, 40, 90, 150, 300])   # cruza 100 em t=4
    assert crossing_hours(traj, threshold=100) == 4.0


def test_crossing_hours_none_quando_nunca_cruza():
    traj = _traj([0, 1, 2, 3, 4])
    assert crossing_hours(traj, threshold=100) is None


def test_lead_time_positivo_quando_detecta_antes():
    traj = _traj([0, 10, 40, 90, 150, 300])   # cruza 100 em t=4
    det = Detection(detector="x", at_hours=1.0, score=1.0)
    assert lead_time_hours(det, traj, threshold=100) == pytest.approx(3.0)


def test_lead_time_negativo_quando_detecta_depois():
    traj = _traj([0, 10, 40, 90, 150, 300])   # cruza 100 em t=4
    det = Detection(detector="x", at_hours=5.0, score=1.0)
    assert lead_time_hours(det, traj, threshold=100) == pytest.approx(-1.0)


def test_lead_time_none_sem_deteccao():
    traj = _traj([0, 10, 40, 90, 150, 300])
    assert lead_time_hours(None, traj, threshold=100) is None


def test_lead_time_none_se_nunca_viraliza():
    traj = _traj([0, 1, 2, 3, 4])
    det = Detection(detector="x", at_hours=1.0, score=1.0)
    assert lead_time_hours(det, traj, threshold=100) is None
