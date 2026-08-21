"""Janela causal — a primitiva anti-vazamento (data leakage) do Motor B.

Data leakage é o erro nº 1 de projeto de ciência de dados: deixar informação do
FUTURO entrar no treino. Aqui a defesa é estrutural — toda feature do Motor B
deve ser calculada só sobre os pontos ATÉ o instante de rotulagem. Esta função é
o gargalo por onde isso passa, e o teste `test_no_leakage.py` a trava.
"""
from __future__ import annotations

import numpy as np

from ..types import Snapshot, Trajectory


def window_before(trajectory: Trajectory, cutoff_hours: float) -> tuple[np.ndarray, np.ndarray]:
    """Devolve (t, views) apenas dos pontos com t <= cutoff_hours.

    É o único caminho permitido para extrair sinal de uma trajetória ao montar
    features: nada calculado depois do corte pode alimentar o modelo.
    """
    t = np.asarray(trajectory.t_hours, dtype=float)
    v = np.asarray(trajectory.views)
    mask = t <= cutoff_hours
    return t[mask], v[mask]


def snapshots_before(snapshots: list[Snapshot], cutoff_hours: float) -> list[Snapshot]:
    """Análogo a `window_before`, mas sobre o histórico BRUTO (`get_snapshots`,
    com likes/comments) em vez de `Trajectory` — é por aqui que `features.py`
    extrai engajamento inicial sem vazar o futuro.

    `cutoff_hours` é relativo ao PRIMEIRO snapshot da lista (mesma convenção
    de `t_hours` em `Trajectory`/`get_trajectory`), ordenados no tempo.
    """
    if not snapshots:
        return []
    ordered = sorted(snapshots, key=lambda s: s.at)
    t0 = ordered[0].at
    return [s for s in ordered if (s.at - t0).total_seconds() / 3600.0 <= cutoff_hours]
