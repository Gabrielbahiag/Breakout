"""Coletor de snapshots — o motor da Fase 0.

Tira uma "foto" das contagens de um conjunto de vídeos e a persiste carimbada
com o tempo do Clock injetado. Rodando periodicamente, é o que constrói as
trajetórias. Note que TODAS as dependências (cliente de API, storage, relógio)
entram pelo construtor — é isso que torna o coletor testável 100% offline.
"""
from __future__ import annotations

from ..contracts import Clock, TrajectoryRepository, YouTubeClient
from ..types import Snapshot


class SnapshotCollector:
    def __init__(
        self,
        client: YouTubeClient,
        repo: TrajectoryRepository,
        clock: Clock,
    ) -> None:
        self._client = client
        self._repo = repo
        self._clock = clock

    def collect_once(self, video_ids: list[str]) -> int:
        """Coleta uma rodada de snapshots. Devolve quantos foram persistidos.

        O cliente devolve contagens SEM tempo; é aqui que carimbamos com
        `clock.now()` — por isso o relógio é injetado e mockável.
        """
        now = self._clock.now()
        stats = self._client.fetch_stats(video_ids)
        for s in stats:
            self._repo.save_snapshot(
                Snapshot(
                    video_id=s.video_id,
                    at=now,
                    views=s.views,
                    likes=s.likes,
                    comments=s.comments,
                )
            )
        return len(stats)
