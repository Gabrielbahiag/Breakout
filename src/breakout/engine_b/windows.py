"""Janela causal — a primitiva anti-vazamento (data leakage) do Motor B.

Data leakage é o erro nº 1 de projeto de ciência de dados: deixar informação do
FUTURO entrar no treino. Aqui a defesa é estrutural — toda feature do Motor B
deve ser calculada só sobre os pontos ATÉ o instante de rotulagem. Esta função é
o gargalo por onde isso passa, e o teste `test_no_leakage.py` a trava.
"""
from __future__ import annotations

import numpy as np

from ..types import Trajectory


def window_before(trajectory: Trajectory, cutoff_hours: float) -> tuple[np.ndarray, np.ndarray]:
    """Devolve (t, views) apenas dos pontos com t <= cutoff_hours.

    É o único caminho permitido para extrair sinal de uma trajetória ao montar
    features: nada calculado depois do corte pode alimentar o modelo.
    """
    t = np.asarray(trajectory.t_hours, dtype=float)
    v = np.asarray(trajectory.views)
    mask = t <= cutoff_hours
    return t[mask], v[mask]
