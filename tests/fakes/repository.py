"""InMemoryTrajectoryRepository — storage de trajetórias em memória.

É um FAKE (implementação real, mas efêmera), não um mock. Honra o Protocol
`TrajectoryRepository`. Guardar snapshots num dict indexado por instante o torna
naturalmente idempotente: recoletar o mesmo vídeo no mesmo tempo sobrescreve, não
duplica — exatamente a garantia que a implementação real (SQLite) precisará dar.

Na integração, dá para trocar por um `SqliteTrajectoryRepository` usando
`sqlite3.connect(":memory:")` sem mudar uma linha dos testes que dependem só do
Protocol.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

from breakout.types import Snapshot, Trajectory, VideoMetadata


class InMemoryTrajectoryRepository:
    def __init__(self) -> None:
        # video_id -> {instante -> Snapshot}  (dedup por instante = idempotência)
        self._snaps: dict[str, dict[datetime, Snapshot]] = {}
        self._meta: dict[str, VideoMetadata] = {}

    def save_snapshot(self, snapshot: Snapshot) -> None:
        self._snaps.setdefault(snapshot.video_id, {})[snapshot.at] = snapshot

    def save_metadata(self, metadata: VideoMetadata) -> None:
        self._meta[metadata.video_id] = metadata

    def get_trajectory(self, video_id: str) -> Trajectory:
        by_time = self._snaps.get(video_id, {})
        if not by_time:
            raise KeyError(f"sem trajetória para {video_id!r}")
        snaps = [by_time[k] for k in sorted(by_time)]
        t0 = snaps[0].at
        t = np.array([(s.at - t0).total_seconds() / 3600.0 for s in snaps], dtype=float)
        views = np.array([s.views for s in snaps], dtype=np.int64)
        return Trajectory(video_id, t, views, self._meta.get(video_id))

    def video_ids(self) -> list[str]:
        return list(self._snaps)
