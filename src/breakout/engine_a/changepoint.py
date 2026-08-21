"""Detectores avançados de ponto de mudança / rajada.

O contrato (Protocol `Detector`) já está fechado; CUSUM (Fase 2), Kleinberg e
BOCPD (Fase 3, evolução) estão implementados aqui. PELT é offline — vive em
`offline.py`, fora do Protocol `Detector`.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import gammaln, logsumexp

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


class BocpdDetector:
    """Bayesian Online Change Point Detection (Adams & MacKay, 2007) — Fase 3
    evolução.

    Diferença estrutural dos outros três: em vez de responder sim/não, mantém
    a cada passo uma distribuição de probabilidade sobre o `run length`
    (quantos passos desde a última mudança de regime). Modela `log1p(taxa)`
    como gaussiana de média/variância desconhecidas por regime (conjugado
    Normal-Gama, preditiva = Student-t) — `log1p` pelo mesmo motivo do
    CUSUM/Kleinberg: a taxa varia ordens de grandeza entre vídeos.

    Duas armadilhas encontradas empiricamente (validadas contra os arquétipos
    sintéticos, não só na teoria) e como este código as evita:

    1. `P(run_length=0)` sozinho é uma identidade matemática da recursão —
       vale exatamente `hazard` em TODO passo, independente dos dados (é um
       fato algébrico da normalização, não carrega sinal nenhum). Quem carrega
       sinal é o `run length` mais provável (MAP) ao longo do tempo: se ele
       vinha crescendo (regime estável) e de repente cai bastante, ISSO é
       mudança de regime de verdade. Por isso o critério aqui é "o MAP já
       esteve estabelecido por `min_run_before_reset` passos e caiu para uma
       FRAÇÃO (`reset_fraction`) do que era" — não olha `P(r=0)` diretamente.
    2. A queda pode ser pra CIMA (rajada começando) ou pra BAIXO (rajada
       acabando, taxa caindo de volta) — o teste de mudança de regime é
       simétrico por natureza. Um `gate` direcional (a taxa nova precisa
       superar a média que o regime estabelecido esperava) filtra só as
       mudanças pra cima, que é o que "decolagem" significa aqui.

    Limitação honesta (não um bug — propriedade do método): BOCPD detecta
    MUDANÇA DE REGIME, então precisa de um período "calmo" estabelecido antes
    da rajada pra ter o que comparar. Isso o torna ótimo pro `SLEEPER` (dorme
    dias, acorda — dispara ANTES até da inflexão nominal, nos testes) mas
    estruturalmente cego pro `ROCKET` (decola quase no upload — não há
    "antes" pra comparar) e pro `SLOW_BURN` (rampa contínua sem quebra
    discreta) — esses dois já são o ponto forte do baseline/CUSUM, que
    detectam ACELERAÇÃO sustentada, não troca de regime.
    """

    def __init__(
        self,
        hazard: float = 1 / 48,
        min_run_before_reset: int = 5,
        reset_fraction: float = 0.5,
        min_points: int = 3,
        mu0: float = 0.0,
        kappa0: float = 0.5,
        alpha0: float = 1.0,
        beta0: float = 1.0,
    ) -> None:
        self.name = "bocpd"
        self.hazard = hazard
        self.min_run_before_reset = min_run_before_reset
        self.reset_fraction = reset_fraction
        self.min_points = min_points
        self._mu0, self._kappa0, self._alpha0, self._beta0 = mu0, kappa0, alpha0, beta0
        self.reset()

    def reset(self) -> None:
        self._prev_t = None
        self._prev_v = None
        self._n = 0
        self._prev_r_map = 0
        self._log_r_probs = np.array([0.0])  # log P(r_0=0) = log(1) = 0
        self._mu = np.array([self._mu0])
        self._kappa = np.array([self._kappa0])
        self._alpha = np.array([self._alpha0])
        self._beta = np.array([self._beta0])

    def update(self, t_hours: float, views: float) -> Detection | None:
        if self._prev_t is None:
            self._prev_t, self._prev_v = t_hours, views
            return None

        dt = t_hours - self._prev_t
        rate = (views - self._prev_v) / dt if dt > 0 else 0.0
        self._prev_t, self._prev_v = t_hours, views
        self._n += 1

        x = math.log1p(max(rate, 0.0))
        # média que o regime ESTABELECIDO esperava, antes de ver `x` — usado
        # só no gate direcional abaixo, não entra na atualização bayesiana.
        established_mu = float(self._mu[self._prev_r_map]) if self._prev_r_map < len(self._mu) else self._mu0

        # preditiva Student-t de cada hipótese de run length ativa.
        df = 2 * self._alpha
        scale2 = self._beta * (self._kappa + 1) / (self._alpha * self._kappa)
        z2 = (x - self._mu) ** 2 / scale2
        pred_log_prob = (
            gammaln((df + 1) / 2)
            - gammaln(df / 2)
            - 0.5 * np.log(df * np.pi * scale2)
            - ((df + 1) / 2) * np.log1p(z2 / df)
        )

        # regra de crescimento/mudança do run length (a mensagem-passing do BOCPD).
        log_growth = self._log_r_probs + pred_log_prob + math.log(1 - self.hazard)
        log_cp = logsumexp(self._log_r_probs + pred_log_prob + math.log(self.hazard))
        new_log_r_probs = np.concatenate([[log_cp], log_growth])
        new_log_r_probs -= logsumexp(new_log_r_probs)

        # update conjugado Normal-Gama: uma hipótese nova (r=0, prior puro) +
        # as que cresceram (r+1, absorveram `x`).
        new_mu = np.concatenate([[self._mu0], (self._kappa * self._mu + x) / (self._kappa + 1)])
        new_kappa = np.concatenate([[self._kappa0], self._kappa + 1])
        new_alpha = np.concatenate([[self._alpha0], self._alpha + 0.5])
        new_beta = np.concatenate(
            [[self._beta0], self._beta + (self._kappa * (x - self._mu) ** 2) / (2 * (self._kappa + 1))]
        )

        self._log_r_probs = new_log_r_probs
        self._mu, self._kappa, self._alpha, self._beta = new_mu, new_kappa, new_alpha, new_beta

        r_map = int(np.argmax(self._log_r_probs))
        prev_r_map = self._prev_r_map
        self._prev_r_map = r_map

        if self._n < self.min_points:
            return None

        reset_happened = prev_r_map >= self.min_run_before_reset and r_map <= prev_r_map * self.reset_fraction
        went_up = x > established_mu
        if reset_happened and went_up:
            score = float(np.exp(self._log_r_probs[r_map]))
            return Detection(detector=self.name, at_hours=t_hours, score=score)
        return None
