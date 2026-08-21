"""Testes do gerador sintético.

O gerador é a fundação de tudo, então ele mesmo precisa ser blindado: as curvas
têm que respeitar os invariantes (monotonicidade, tempo ordenado) para QUALQUER
seed, a verdade-conhecida tem que ser coerente, e a geração tem que ser
reprodutível. Aqui é onde `Hypothesis` brilha — prova propriedades sobre um
espaço de seeds, não só um exemplo.
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from breakout.synth.trajectories import VIRAL_THRESHOLD_DEFAULT, make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


def test_todos_arquetipos_geram_curva(any_archetype):
    traj, truth = make_trajectory(any_archetype, seed=1)
    assert traj.views.shape == traj.t_hours.shape
    assert traj.views.size == 72
    assert truth.archetype is any_archetype


@given(seed=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=50, deadline=None)
def test_views_sao_monotonicas_para_qualquer_seed(seed):
    # Propriedade: views é cumulativa, então NUNCA decresce — em nenhum seed.
    for arch in Archetype:
        traj, _ = make_trajectory(arch, seed=seed)
        assert np.all(np.diff(traj.views) >= 0), f"{arch} quebrou monotonicidade no seed {seed}"


@given(seed=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=50, deadline=None)
def test_tempo_comeca_em_zero_e_e_ordenado(seed):
    traj, _ = make_trajectory(Archetype.ROCKET, seed=seed)
    assert traj.t_hours[0] == 0.0
    assert np.all(np.diff(traj.t_hours) > 0)


def test_reprodutibilidade_por_seed():
    a, _ = make_trajectory(Archetype.SLOW_BURN, seed=42)
    b, _ = make_trajectory(Archetype.SLOW_BURN, seed=42)
    c, _ = make_trajectory(Archetype.SLOW_BURN, seed=43)
    assert np.array_equal(a.views, b.views)          # mesmo seed -> idêntico
    assert not np.array_equal(a.views, c.views)      # seed diferente -> diferente


@pytest.mark.parametrize(
    "archetype,expected_viral",
    [
        (Archetype.ROCKET, True),
        (Archetype.SLOW_BURN, True),
        (Archetype.SLEEPER, True),
        (Archetype.FLASH_IN_PAN, False),
        (Archetype.STILLBORN, False),
    ],
)
def test_rotulo_viral_coerente_com_teto(archetype, expected_viral):
    # A verdade-conhecida do rótulo bate com o teto atingido pela curva.
    traj, truth = make_trajectory(archetype, seed=7)
    assert truth.is_viral is expected_viral
    assert (truth.ceiling_views >= VIRAL_THRESHOLD_DEFAULT) is expected_viral
    assert float(traj.views[-1]) == truth.ceiling_views


def test_arquetipos_sem_decolagem_tem_takeoff_none():
    _, truth = make_trajectory(Archetype.STILLBORN, seed=1)
    assert truth.takeoff_hours is None
