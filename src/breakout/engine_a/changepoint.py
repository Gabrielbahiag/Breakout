"""Detectores avançados de ponto de mudança / rajada.

O contrato (Protocol `Detector`) já está fechado; CUSUM (Fase 2) e Kleinberg
(Fase 3) estão implementados aqui. BOCPD/PELT continuam como evolução futura.
"""
from __future__ import annotations

import math

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
    """Autômato de rajada de Kleinberg (2002) — Fase 3.

    Adaptação ONLINE do autômato de estados do paper original para uma série
    de TAXA (views/hora) em vez da sequência de gaps entre eventos: o estado
    `i` "espera" uma taxa `baseline * s**i` (estado 0 = normal; estados > 0 =
    níveis crescentes de rajada). É um Viterbi incremental — a cada ponto,
    atualiza o custo mínimo acumulado de estar em cada estado (emissão: erro
    quadrático em escala LOG entre taxa observada e taxa esperada do estado —
    mesmo truque de robustez a escala do CUSUM; transição: `gamma * (i - j)`
    para SUBIR de estado, descer é de graça — rajada é difícil de começar,
    fácil de acabar). O estado corrente é o argmin; dispara quando ele sai do
    estado 0.

    Simplificação deliberada frente ao paper: a transição não escala com
    `ln(n)` (lá, uma série mais longa exige mais evidência pra rajada) — aqui
    o comportamento fica estável para séries de qualquer tamanho, o que faz
    mais sentido para um detector que roda indefinidamente.
    """

    def __init__(
        self,
        states: int = 2,
        gamma: float = 1.0,
        s: float = 3.0,
        alpha: float = 0.05,
        min_points: int = 3,
    ) -> None:
        self.name = "kleinberg"
        self.states = states
        self.gamma = gamma
        self.s = s
        self.alpha = alpha
        self.min_points = min_points
        self.reset()

    def reset(self) -> None:
        self._prev_t = None
        self._prev_v = None
        self._n = 0
        self._baseline_rate = None
        self._cost = [0.0] * self.states

    def update(self, t_hours: float, views: float) -> Detection | None:
        # Primeiro ponto: ainda não há taxa.
        if self._prev_t is None:
            self._prev_t, self._prev_v = t_hours, views
            return None

        dt = t_hours - self._prev_t
        rate = (views - self._prev_v) / dt if dt > 0 else 0.0
        self._prev_t, self._prev_v = t_hours, views
        self._n += 1

        # EWMA lento: o estado 0 (baseline) não pode "normalizar" a própria
        # rajada rápido demais, senão o detector perde o sinal no meio dela.
        # Inicializa NA primeira taxa observada (não em 0.0) — senão a partida
        # fria por si só parece rajada nos primeiros pontos.
        if self._baseline_rate is None:
            self._baseline_rate = rate
        else:
            self._baseline_rate = self.alpha * rate + (1 - self.alpha) * self._baseline_rate

        eps = 1.0
        log_rate = math.log(rate + eps)
        expected = [math.log(self._baseline_rate * (self.s**i) + eps) for i in range(self.states)]
        emission = [(log_rate - expected[i]) ** 2 for i in range(self.states)]

        new_cost = [
            min(self._cost[j] + self.gamma * max(0, i - j) for j in range(self.states)) + emission[i]
            for i in range(self.states)
        ]
        state = min(range(self.states), key=lambda i: new_cost[i])
        floor = new_cost[state]
        self._cost = [c - floor for c in new_cost]  # normaliza: evita custo crescer sem limite

        if self._n < self.min_points:
            return None

        if state > 0:
            return Detection(detector=self.name, at_hours=t_hours, score=float(state))
        return None
