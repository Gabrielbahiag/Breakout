"""Detectores avançados de ponto de mudança / rajada — IMPLEMENTAÇÃO PENDENTE.

O contrato (Protocol `Detector`) já está fechado; estes são os alvos das
próximas fases. Os testes correspondentes existem e estão marcados como `xfail`
(esperando NotImplementedError): quando você implementar, o xfail vira "xpass" e
te avisa que está pronto. É o "test-first" na prática.
"""
from __future__ import annotations

from ..types import Detection


class CusumDetector:
    """CUSUM / Page-Hinkley (one-sided, só detecta ALTA na taxa) — Fase 2.

    Mantém a média cumulativa online da taxa (views/hora) e acumula o desvio
    acima dela, descontado um `drift` de tolerância (ruído pequeno não conta).
    Esse acumulado (`PH_T`, o clássico da literatura de Page-Hinkley) só cresce
    quando a série muda de regime de verdade; dispara quando ele se afasta do
    seu próprio mínimo histórico (`PH_T - min(PH)`) além do `threshold`.

    Por que funciona sem normalizar por escala: os arquétipos que decolam têm
    taxa de pico ordens de grandeza acima do STILLBORN (a taxa-base), então um
    par (threshold, drift) fixo em unidades absolutas de views/hora já separa
    os dois regimes — o mesmo truque do `floor` do baseline.
    """

    def __init__(
        self,
        threshold: float = 3_000.0,
        drift: float = 200.0,
        min_points: int = 3,
    ) -> None:
        self.name = "cusum"
        self.threshold = threshold
        self.drift = drift
        self.min_points = min_points
        self.reset()

    def reset(self) -> None:
        self._prev_t = None
        self._prev_v = None
        self._n = 0
        self._mean = 0.0
        self._cum = 0.0
        self._cum_min = 0.0

    def update(self, t_hours: float, views: float) -> Detection | None:
        # Primeiro ponto: ainda não há taxa.
        if self._prev_t is None:
            self._prev_t, self._prev_v = t_hours, views
            return None

        dt = t_hours - self._prev_t
        rate = (views - self._prev_v) / dt if dt > 0 else 0.0
        self._prev_t, self._prev_v = t_hours, views

        self._n += 1
        self._mean += (rate - self._mean) / self._n  # média cumulativa online
        self._cum += rate - self._mean - self.drift
        self._cum_min = min(self._cum_min, self._cum)

        if self._n < self.min_points:
            return None

        score = self._cum - self._cum_min
        if score > self.threshold:
            return Detection(detector=self.name, at_hours=t_hours, score=float(score))
        return None


class KleinbergBurstDetector:
    """Autômato de rajada de Kleinberg — o algoritmo canônico (Fase 3)."""

    def __init__(self, states: int = 2, gamma: float = 1.0) -> None:
        self.name = "kleinberg"
        self.states = states
        self.gamma = gamma

    def update(self, t_hours: float, views: float) -> Detection | None:
        raise NotImplementedError("Fase 3: implementar autômato de Kleinberg")

    def reset(self) -> None:
        pass
