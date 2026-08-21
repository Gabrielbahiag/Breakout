"""Segmentação OFFLINE de trajetórias — PELT (Fase 3, evolução).

Diferença estrutural dos detectores do Protocol `Detector` (baseline/CUSUM/
Kleinberg/BOCPD, que decidem ponto a ponto vendo só o passado): o PELT
(*Pruned Exact Linear Time*, via `ruptures`) recebe a trajetória INTEIRA de
uma vez e acha o conjunto ÓTIMO de pontos de mudança — não serve pra alarme em
tempo real, serve pra ANOTAR retroativamente onde a decolagem aconteceu em
curvas já coletadas (sintéticas ou reais). É o dado de treino que falta pra
avaliar os detectores online contra vídeos reais, onde ninguém sabe de
antemão a verdade.
"""
from __future__ import annotations

import numpy as np
import ruptures as rpt

from ..types import Trajectory


def segment(trajectory: Trajectory, *, penalty: float = 20.0, model: str = "l2") -> list[float]:
    """Acha os instantes (`t_hours`) que segmentam a trajetória em regimes.

    Trabalha sobre `log1p(taxa)` (views/hora), não sobre views cumulativas —
    é a TAXA que muda de regime; o total acumulado é sempre monótono
    crescente e nunca teria uma "mudança de nível" detectável dessa forma.
    `log1p` pelo mesmo motivo do CUSUM/Kleinberg/BOCPD: a taxa varia ordens
    de grandeza entre vídeos, então o custo precisa ser robusto a escala.

    `penalty` controla a granularidade da segmentação (maior = menos
    segmentos). Devolve os instantes de mudança — não inclui o fim da série.
    """
    if trajectory.views.size < 3:
        return []

    dt = np.diff(trajectory.t_hours)
    rate = np.diff(trajectory.views) / np.where(dt > 0, dt, 1.0)
    rate = np.clip(rate, 0.0, None)
    signal = np.log1p(rate)

    algo = rpt.Pelt(model=model, min_size=2, jump=1).fit(signal.reshape(-1, 1))
    breakpoints = algo.predict(pen=penalty)  # índices em `signal`; o último = len(signal)

    # signal[i] é a taxa no intervalo (t[i], t[i+1]]; um breakpoint em i
    # (início do novo segmento) corresponde ao instante t[i+1].
    t_after = trajectory.t_hours[1:]  # mesmo tamanho de `signal`
    return [float(t_after[i]) for i in breakpoints[:-1]]
