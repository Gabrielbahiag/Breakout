"""Testes dos detectores avançados — em estado 'test-first'.

O contrato já está fechado, a implementação não. Marcamos como `xfail(raises=
NotImplementedError)`: enquanto não implementado, o teste "falha como esperado"
(xfail). No dia em que você implementar o CUSUM na IDE, ele passa e o pytest
reporta `XPASS`, te avisando que a feature ficou pronta. É o roteiro da Fase 2/3.
"""
from __future__ import annotations

import pytest

from breakout.engine_a.changepoint import CusumDetector, KleinbergBurstDetector
from breakout.engine_a.replay import run_detector
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


@pytest.mark.xfail(raises=NotImplementedError, reason="Fase 2: CUSUM/Page-Hinkley")
def test_cusum_dispara_em_rocket():
    traj, _ = make_trajectory(Archetype.ROCKET, seed=1)
    hit = run_detector(CusumDetector(), traj)
    assert hit is not None


@pytest.mark.xfail(raises=NotImplementedError, reason="Fase 3: autômato de Kleinberg")
def test_kleinberg_dispara_em_rocket():
    traj, _ = make_trajectory(Archetype.ROCKET, seed=1)
    hit = run_detector(KleinbergBurstDetector(), traj)
    assert hit is not None
