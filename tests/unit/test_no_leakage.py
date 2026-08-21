"""Teste-guarda anti-vazamento (data leakage).

Este é o teste que impressiona em entrevista: uma barreira estrutural contra o
erro nº 1 de ciência de dados. Ele garante que a extração de features do Motor B
JAMAIS enxerga pontos posteriores ao instante de rotulagem. Se alguém, um dia,
tentar calcular uma feature usando o futuro, este teste quebra.
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from breakout.engine_b.windows import window_before
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.unit


@given(cutoff=st.floats(min_value=0, max_value=71), seed=st.integers(0, 1000))
@settings(max_examples=50, deadline=None)
def test_janela_nunca_devolve_o_futuro(cutoff, seed):
    traj, _ = make_trajectory(Archetype.ROCKET, seed=seed)
    t, _v = window_before(traj, cutoff)
    assert np.all(t <= cutoff)


def test_janela_e_prefixo_da_trajetoria():
    traj, _ = make_trajectory(Archetype.SLOW_BURN, seed=1)
    t, v = window_before(traj, cutoff_hours=10.0)
    # É exatamente o prefixo t<=10, na ordem original.
    assert np.array_equal(t, traj.t_hours[traj.t_hours <= 10.0])
    assert np.array_equal(v, traj.views[traj.t_hours <= 10.0])


def test_cutoff_zero_devolve_so_o_primeiro_ponto():
    traj, _ = make_trajectory(Archetype.ROCKET, seed=1)
    t, _v = window_before(traj, cutoff_hours=0.0)
    assert t.tolist() == [0.0]
