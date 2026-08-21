"""Gerador de trajetórias sintéticas com verdade-conhecida.

Este é o ativo de teste de maior alavancagem do Breakout. Ele produz curvas de
views-no-tempo com ponto de decolagem *rotulado* e teto *conhecido*. Com isso:

  - dá para medir LEAD TIME exato (você sabe onde foi a decolagem);
  - dá para rodar TODOS os detectores contra as MESMAS curvas (bake-off);
  - desbloqueia o Motor A inteiro na Fase 0, sem esperar o coletor real acumular
    semanas de dados;
  - o mesmo truque (plantar sinal conhecido) valida o Motor B: "vídeos com número
    no título viralizam 3x mais, por construção" -> "o modelo acha o sinal?".

Por que também vive em `src/` (e não só em `tests/`): a geração de curvas com
ground truth é uma feature de primeira classe — alimenta o modo replay/simulação
e os demos do README, não só a suíte de testes.

Modelo: cada arquétipo é uma logística (curva-S) cumulativa. Geramos os
INCREMENTOS por hora (sempre >= 0), aplicamos ruído multiplicativo lognormal
(sempre positivo) e fazemos cumsum -> garante que views é monótona por
construção. Determinístico dado o `seed`.
"""
from __future__ import annotations

import numpy as np

from ..types import Archetype, GroundTruth, Trajectory, VideoMetadata

# Limiar padrão de "viral" (views). A definição real é plugável no label.py;
# aqui serve só para carimbar a verdade-conhecida de forma consistente.
VIRAL_THRESHOLD_DEFAULT = 100_000

# Parâmetros de cada arquétipo: L = teto, k = inclinação, t0 = hora da inflexão.
_PARAMS: dict[Archetype, dict[str, float]] = {
    Archetype.ROCKET: dict(L=2_000_000, k=0.5, t0=6.0),
    Archetype.SLOW_BURN: dict(L=1_200_000, k=0.12, t0=48.0),
    Archetype.SLEEPER: dict(L=1_500_000, k=0.6, t0=40.0),
    Archetype.FLASH_IN_PAN: dict(L=30_000, k=0.6, t0=5.0),
    Archetype.STILLBORN: dict(L=2_000, k=0.05, t0=36.0),
}

# Arquétipos que de fato têm uma inflexão verdadeira (takeoff conhecido).
_HAS_TAKEOFF = {
    Archetype.ROCKET,
    Archetype.SLOW_BURN,
    Archetype.SLEEPER,
    Archetype.FLASH_IN_PAN,
}


def _logistic(t: np.ndarray, L: float, k: float, t0: float) -> np.ndarray:
    return L / (1.0 + np.exp(-k * (t - t0)))


def make_trajectory(
    archetype: Archetype,
    *,
    hours: int = 72,
    step_h: float = 1.0,
    seed: int = 0,
    noise: float = 0.15,
    threshold: int = VIRAL_THRESHOLD_DEFAULT,
    video_id: str | None = None,
    metadata: VideoMetadata | None = None,
) -> tuple[Trajectory, GroundTruth]:
    """Gera uma (Trajectory, GroundTruth) para o arquétipo pedido.

    `noise` é o sigma do ruído lognormal aplicado aos incrementos por hora.
    Determinístico dado o `seed`.
    """
    if archetype not in _PARAMS:
        raise ValueError(f"arquétipo desconhecido: {archetype!r}")

    rng = np.random.default_rng(seed)
    params = _PARAMS[archetype]

    t = np.arange(0, hours, step_h, dtype=float)
    clean = _logistic(t, **params)
    clean = clean - clean[0]                      # começa em ~0
    increments = np.clip(np.diff(clean, prepend=0.0), 0.0, None)
    factor = rng.lognormal(mean=0.0, sigma=noise, size=increments.shape)
    views = np.round(np.cumsum(increments * factor)).astype(np.int64)

    ceiling = float(views[-1])
    is_viral = ceiling >= threshold
    takeoff = float(params["t0"]) if archetype in _HAS_TAKEOFF else None

    truth = GroundTruth(
        archetype=archetype,
        is_viral=is_viral,
        takeoff_hours=takeoff,
        ceiling_views=ceiling,
    )
    traj = Trajectory(
        video_id=video_id or f"{archetype.value}_{seed}",
        t_hours=t,
        views=views,
        metadata=metadata,
    )
    return traj, truth


def make_batch(
    *, per_archetype: int = 5, hours: int = 72, base_seed: int = 0, noise: float = 0.15
) -> list[tuple[Trajectory, GroundTruth]]:
    """Uma bateria com todos os arquétipos, para o bake-off de detectores."""
    out: list[tuple[Trajectory, GroundTruth]] = []
    seed = base_seed
    for arch in Archetype:
        for _ in range(per_archetype):
            out.append(make_trajectory(arch, hours=hours, seed=seed, noise=noise))
            seed += 1
    return out
