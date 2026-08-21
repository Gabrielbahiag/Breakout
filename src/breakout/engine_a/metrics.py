"""Métricas do Motor A — o 'pulo do gato' do projeto.

A métrica central é o LEAD TIME: quantas horas ANTES de o vídeo cruzar o limiar
de "viral" o detector disparou. Positivo = detectou antes (bom). Negativo =
detectou depois (chegou atrasado). É isso que separa um detector útil de um
alarme que só confirma o óbvio.

Sobre earliness x acurácia, precisão/recall dos alarmes e a curva de trade-off:
ficam para a Fase 2 (`benchmark.py`), construídos sobre `lead_time_hours`.
"""
from __future__ import annotations

import numpy as np

from ..types import Detection, Trajectory


def crossing_hours(trajectory: Trajectory, threshold: int) -> float | None:
    """Hora em que as views cruzam `threshold` pela primeira vez, ou None se
    nunca cruzam (o caso dos vídeos que não viralizam)."""
    mask = np.asarray(trajectory.views) >= threshold
    if not mask.any():
        return None
    return float(trajectory.t_hours[int(np.argmax(mask))])


def lead_time_hours(
    detection: Detection | None, trajectory: Trajectory, threshold: int
) -> float | None:
    """Lead time = (hora do cruzamento do limiar) - (hora da detecção).

    Retorna None quando não há detecção ou quando o vídeo nunca cruza o limiar
    (não dá para ter lead time sobre um evento que não aconteceu).
    """
    if detection is None:
        return None
    crossing = crossing_hours(trajectory, threshold)
    if crossing is None:
        return None
    return crossing - detection.at_hours
