"""Testes do detector baseline.

Nota importante de honestidade científica: aqui NÃO afirmamos números de lead
time (isso é qualidade de detector, assunto do benchmark da Fase 2). Afirmamos
apenas PROPRIEDADES estruturais que qualquer detector são precisa respeitar:

  - nunca dispara no primeiro ponto (sem taxa não há sinal);
  - dispara nos arquétipos que de fato decolam;
  - fica em silêncio no arquétipo morto (a taxa-base / controle).

Essas são as invariantes do contrato, não a promessa de "fórmula do viral".
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from breakout.engine_a.baseline import BaselineDetector
from breakout.engine_a.replay import run_detector
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


def test_honra_o_contrato_detector():
    from breakout.contracts import Detector

    assert isinstance(BaselineDetector(), Detector)


@given(seed=st.integers(min_value=0, max_value=2_000))
@settings(max_examples=30, deadline=None)
def test_nunca_dispara_no_primeiro_ponto(seed):
    det = BaselineDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=seed)
    first_t, first_v = next(traj.stream())
    det.reset()
    assert det.update(first_t, first_v) is None


@pytest.mark.parametrize("archetype", [Archetype.ROCKET, Archetype.SLEEPER, Archetype.SLOW_BURN])
def test_dispara_nos_arquetipos_que_decolam(archetype):
    det = BaselineDetector()
    traj, _ = make_trajectory(archetype, seed=3)
    hit = run_detector(det, traj)
    assert hit is not None
    assert hit.at_hours > 0            # nunca no instante inicial
    assert hit.at_hours <= traj.t_hours[-1]


def test_silencia_no_arquetipo_morto():
    det = BaselineDetector()
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    assert run_detector(det, traj) is None


def test_reset_permite_reprocessar():
    det = BaselineDetector()
    traj, _ = make_trajectory(Archetype.ROCKET, seed=5)
    first = run_detector(det, traj)
    second = run_detector(det, traj)   # run_detector já chama reset()
    assert first == second             # determinístico
