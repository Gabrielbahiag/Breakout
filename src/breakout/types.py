"""Tipos centrais do domínio Breakout.

Estes dataclasses são o vocabulário compartilhado pelos dois motores. Manter
tudo aqui (e não espalhado) é o que permite que coletor, storage, detectores e
classificador conversem sem se acoplar às implementações uns dos outros.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np


@dataclass(frozen=True, slots=True)
class RawStats:
    """Contagens cruas devolvidas pela fronteira de API, ainda SEM timestamp.

    Quem carimba o tempo é o coletor (usando o Clock injetado), não o cliente —
    por isso o tempo não vive aqui. Isso mantém o relógio como dependência
    explícita e testável.
    """

    video_id: str
    views: int
    likes: int = 0
    comments: int = 0


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Uma observação de um vídeo num instante. A unidade da coleta."""

    video_id: str
    at: datetime
    views: int
    likes: int = 0
    comments: int = 0


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Metadados quase-estáticos do vídeo. Insumo do Motor B."""

    video_id: str
    channel_id: str
    title: str
    duration_s: int
    published_at: datetime
    channel_subscribers: int = 0
    tags: tuple[str, ...] = ()
    category: str = "unknown"
    thumbnail_url: str = ""    # Motor B multimodal (Fase 5): CV
    transcript: str = ""       # Motor B multimodal (Fase 5): legendas


@dataclass(slots=True)
class Trajectory:
    """A curva de crescimento de um vídeo: views cumulativas ao longo do tempo.

    `t_hours` são horas desde a publicação (float, ordenado). `views` são
    contagens cumulativas (inteiras, monótonas não-decrescentes). Essa é a
    entrada canônica do Motor A.

    A API do YouTube pode devolver uma contagem MENOR que a anterior (remoção
    de views fraudulentas/de bot) — o snapshot bruto guarda isso fielmente
    (Princípio 1, núcleo append-only), mas quem constrói uma `Trajectory` a
    partir de snapshots (`get_trajectory()`) precisa suavizar pro máximo
    corrido ANTES de chegar aqui — este construtor não aceita queda.
    """

    video_id: str
    t_hours: np.ndarray
    views: np.ndarray
    metadata: VideoMetadata | None = None

    def __post_init__(self) -> None:
        t = np.asarray(self.t_hours, dtype=float)
        v = np.asarray(self.views)
        if t.shape != v.shape:
            raise ValueError("t_hours e views precisam ter o mesmo tamanho")
        if t.size and np.any(np.diff(t) < 0):
            raise ValueError("t_hours precisa estar em ordem cronológica")
        if v.size and np.any(np.diff(v) < 0):
            raise ValueError("views precisa ser monótona não-decrescente (é cumulativa)")
        # normaliza os tipos guardados (arrays numpy)
        self.t_hours = t
        self.views = v

    def stream(self):
        """Itera (t, view) ponto-a-ponto, como se os dados chegassem ao vivo."""
        for t, v in zip(self.t_hours, self.views):
            yield float(t), float(v)


class Archetype(str, Enum):
    """Arquétipos de trajetória de viralização. Cada um estressa o detector de
    um jeito diferente — e cada um é uma feature candidata do projeto."""

    ROCKET = "rocket"            # decola quase no upload
    SLOW_BURN = "slow_burn"      # sobe devagar, estoura tarde (sinal fraco)
    SLEEPER = "sleeper"          # morto por dias, depois acorda
    FLASH_IN_PAN = "flash_in_pan"  # sobe rápido e murcha (falso positivo)
    STILLBORN = "stillborn"      # nunca sai do chão (a taxa-base / controle)


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """A verdade-conhecida de uma trajetória sintética. É o que torna possível
    medir lead time com exatidão — o coletor real nunca te dá isso."""

    archetype: Archetype
    is_viral: bool
    takeoff_hours: float | None   # instante verdadeiro da inflexão; None se nunca decola
    ceiling_views: float          # teto (assíntota) da curva


@dataclass(frozen=True, slots=True)
class Detection:
    """O momento em que um detector dispara: 'este vídeo está decolando agora'."""

    detector: str
    at_hours: float   # quando disparou (horas desde publicação)
    score: float      # força/confiança do sinal
