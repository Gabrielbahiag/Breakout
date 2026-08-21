"""Detectores avançados de ponto de mudança / rajada — IMPLEMENTAÇÃO PENDENTE.

O contrato (Protocol `Detector`) já está fechado; estes são os alvos das
próximas fases. Os testes correspondentes existem e estão marcados como `xfail`
(esperando NotImplementedError): quando você implementar, o xfail vira "xpass" e
te avisa que está pronto. É o "test-first" na prática.
"""
from __future__ import annotations

from ..types import Detection


class CusumDetector:
    """CUSUM / Page-Hinkley — detecção clássica de salto na taxa (Fase 2)."""

    def __init__(self, threshold: float = 5.0, drift: float = 0.0) -> None:
        self.name = "cusum"
        self.threshold = threshold
        self.drift = drift

    def update(self, t_hours: float, views: float) -> Detection | None:
        raise NotImplementedError("Fase 2: implementar CUSUM/Page-Hinkley")

    def reset(self) -> None:
        pass


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
