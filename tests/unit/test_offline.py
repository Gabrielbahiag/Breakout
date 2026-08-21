"""Testes do PELT offline (`offline.py::segment`).

Diferente dos detectores online (Protocol `Detector`), o PELT não responde
"disparou/não disparou" — devolve uma LISTA de instantes de mudança. As
propriedades testadas são análogas em espírito às dos detectores online:
encontra estrutura nos arquétipos que decolam, fica em silêncio (lista vazia)
no STILLBORN, nunca aponta o instante inicial, é determinístico.
"""
from __future__ import annotations

import pytest

from breakout.engine_a.offline import segment
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "archetype",
    [Archetype.ROCKET, Archetype.SLOW_BURN, Archetype.SLEEPER, Archetype.FLASH_IN_PAN],
)
def test_encontra_pelo_menos_um_changepoint_nos_arquetipos_que_decolam(archetype):
    traj, _ = make_trajectory(archetype, seed=3)
    cps = segment(traj)
    assert len(cps) >= 1
    assert all(0 < cp <= traj.t_hours[-1] for cp in cps)


def test_silencia_no_arquetipo_morto():
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    assert segment(traj) == []


def test_changepoints_em_ordem_cronologica():
    traj, _ = make_trajectory(Archetype.SLEEPER, seed=3)
    cps = segment(traj)
    assert cps == sorted(cps)


def test_deterministico():
    traj, _ = make_trajectory(Archetype.ROCKET, seed=5)
    assert segment(traj) == segment(traj)


def test_trajetoria_curta_demais_nao_quebra():
    from breakout.types import Trajectory
    import numpy as np

    traj = Trajectory("curta", np.array([0.0, 1.0]), np.array([0, 10]))
    assert segment(traj) == []
