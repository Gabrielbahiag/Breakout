"""Testes dos detectores avançados.

CUSUM e Kleinberg (Fase 3) seguem as mesmas propriedades estruturais de
`test_baseline.py` (nunca dispara no primeiro ponto, dispara nos arquétipos
que decolam, silencia no STILLBORN, é determinístico).

BOCPD (Fase 3, evolução) é estruturalmente diferente: detecta MUDANÇA DE
REGIME, não aceleração — por isso só é testado disparando no `SLEEPER`
(dorme, depois acorda: tem um "antes" calmo pra comparar), não em
ROCKET/SLOW_BURN (rampas contínuas, sem período calmo prévio — limitação
honesta do método, documentada no docstring da classe, não uma falha de
implementação).
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from breakout.engine_a.changepoint import BocpdDetector, CusumDetector, KleinbergBurstDetector
from breakout.engine_a.replay import run_detector
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


def test_cusum_honra_o_contrato_detector():
    from breakout.contracts import Detector

    assert isinstance(CusumDetector(), Detector)


@given(seed=st.integers(min_value=0, max_value=2_000))
@settings(max_examples=30, deadline=None)
def test_cusum_nunca_dispara_no_primeiro_ponto(seed):
    det = CusumDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=seed)
    first_t, first_v = next(traj.stream())
    det.reset()
    assert det.update(first_t, first_v) is None


@pytest.mark.parametrize("archetype", [Archetype.ROCKET, Archetype.SLEEPER, Archetype.SLOW_BURN])
def test_cusum_dispara_nos_arquetipos_que_decolam(archetype):
    det = CusumDetector()
    traj, _ = make_trajectory(archetype, seed=3)
    hit = run_detector(det, traj)
    assert hit is not None
    assert hit.at_hours > 0            # nunca no instante inicial
    assert hit.at_hours <= traj.t_hours[-1]


def test_cusum_silencia_no_arquetipo_morto():
    det = CusumDetector()
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    assert run_detector(det, traj) is None


def test_cusum_reset_permite_reprocessar():
    det = CusumDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=5)
    first = run_detector(det, traj)
    second = run_detector(det, traj)   # run_detector já chama reset()
    assert first == second             # determinístico


def test_kleinberg_honra_o_contrato_detector():
    from breakout.contracts import Detector

    assert isinstance(KleinbergBurstDetector(), Detector)


@given(seed=st.integers(min_value=0, max_value=2_000))
@settings(max_examples=30, deadline=None)
def test_kleinberg_nunca_dispara_no_primeiro_ponto(seed):
    det = KleinbergBurstDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=seed)
    first_t, first_v = next(traj.stream())
    det.reset()
    assert det.update(first_t, first_v) is None


@pytest.mark.parametrize("archetype", [Archetype.ROCKET, Archetype.SLEEPER, Archetype.SLOW_BURN])
def test_kleinberg_dispara_nos_arquetipos_que_decolam(archetype):
    det = KleinbergBurstDetector()
    traj, _ = make_trajectory(archetype, seed=3)
    hit = run_detector(det, traj)
    assert hit is not None
    assert hit.at_hours > 0
    assert hit.at_hours <= traj.t_hours[-1]


def test_kleinberg_silencia_no_arquetipo_morto():
    det = KleinbergBurstDetector()
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    assert run_detector(det, traj) is None


def test_kleinberg_reset_permite_reprocessar():
    det = KleinbergBurstDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=5)
    first = run_detector(det, traj)
    second = run_detector(det, traj)
    assert first == second


def test_bocpd_honra_o_contrato_detector():
    from breakout.contracts import Detector

    assert isinstance(BocpdDetector(), Detector)


@given(seed=st.integers(min_value=0, max_value=2_000))
@settings(max_examples=30, deadline=None)
def test_bocpd_nunca_dispara_no_primeiro_ponto(seed):
    det = BocpdDetector()
    traj, _ = make_trajectory(Archetype.SLEEPER, seed=seed)
    first_t, first_v = next(traj.stream())
    det.reset()
    assert det.update(first_t, first_v) is None


@given(seed=st.integers(min_value=0, max_value=500))
@settings(max_examples=40, deadline=None)
def test_bocpd_dispara_no_sleeper_antes_da_inflexao_nominal(seed):
    det = BocpdDetector()
    traj, truth = make_trajectory(Archetype.SLEEPER, seed=seed)
    hit = run_detector(det, traj)
    assert hit is not None
    assert hit.at_hours > 0
    # a vantagem do BOCPD: pega o "acordar" antes da inflexão formal da curva.
    assert hit.at_hours < truth.takeoff_hours


def test_bocpd_silencia_no_arquetipo_morto():
    det = BocpdDetector()
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    assert run_detector(det, traj) is None


def test_bocpd_reset_permite_reprocessar():
    det = BocpdDetector()
    traj, _ = make_trajectory(Archetype.SLEEPER, seed=5)
    first = run_detector(det, traj)
    second = run_detector(det, traj)
    assert first == second
