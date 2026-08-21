"""Detector baseline — a Camada 1 do Motor A: velocidade e aceleração.

Ideia (deliberadamente simples, é o baseline): suavizar a taxa de crescimento
(views/hora) com EWMA e disparar quando ela está ACELERANDO de forma sustentada
— aceleração positiva por vários passos — desde que a taxa já esteja acima de um
piso (o que cala o vídeo morto, cuja taxa é ruído em torno de ~zero).

Por que aceleração e não salto relativo: um "foguete" decola já na 1a hora e não
oferece nenhum período calmo para estimar uma linha de base — mas a aceleração
positiva da curva-S ainda é visível. Aceleração é o sinal robusto que atravessa
todos os arquétipos.

Detectores mais fortes (CUSUM/Page-Hinkley, Kleinberg, BOCPD) entram como
implementações intercambiáveis do mesmo Protocol `Detector` nas fases seguintes.
"""
from __future__ import annotations

from ..types import Detection


class BaselineDetector:
    """Detecção online por aceleração sustentada da taxa suavizada.

    Parâmetros:
        alpha: fator do EWMA da taxa (maior = mais reativo).
        min_points: no minimo de pontos antes de poder disparar (nunca em t=0).
        sustain: passos consecutivos de aceleracao positiva para confirmar.
        floor: taxa minima (views/h) para o sinal contar — filtra video morto.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        min_points: int = 3,
        sustain: int = 3,
        floor: float = 100.0,
    ) -> None:
        self.name = "baseline_accel"
        self.alpha = alpha
        self.min_points = min_points
        self.sustain = sustain
        self.floor = floor
        self.reset()

    def reset(self) -> None:
        self._prev_t = None
        self._prev_v = None
        self._ewma = None
        self._prev_ewma = None
        self._streak = 0
        self._n = 0

    def update(self, t_hours: float, views: float) -> Detection | None:
        self._n += 1

        # Primeiro ponto: ainda nao ha taxa.
        if self._prev_t is None:
            self._prev_t, self._prev_v = t_hours, views
            return None

        dt = t_hours - self._prev_t
        rate = (views - self._prev_v) / dt if dt > 0 else 0.0
        self._prev_t, self._prev_v = t_hours, views

        self._ewma = rate if self._ewma is None else self.alpha * rate + (1 - self.alpha) * self._ewma

        # Precisamos de dois pontos de EWMA para ter aceleracao.
        if self._prev_ewma is None:
            self._prev_ewma = self._ewma
            return None

        accel = self._ewma - self._prev_ewma
        self._prev_ewma = self._ewma

        if self._n < self.min_points:
            return None

        if accel > 0 and self._ewma > self.floor:
            self._streak += 1
            if self._streak >= self.sustain:
                return Detection(detector=self.name, at_hours=t_hours, score=float(self._ewma))
        else:
            self._streak = 0
        return None
