"""Repositório SQL — a implementação real do contrato `TrajectoryRepository`.

O ponto central: este código NÃO sabe se está falando com um SQLite local (dev)
ou com o Turso na nuvem (produção). Ele recebe uma conexão DB-API pronta e opera
sobre ela. Como Turso/libSQL é SQLite-compatível, o mesmo SQL roda nos dois — a
troca dev↔prod é escolher a conexão no composition root, não reescrever nada.

Isto é o contrato pagando o aluguel: os testes rodam este repositório contra um
sqlite `:memory:` e provam que ele honra o mesmo contrato que o fake em memória.
"""
from __future__ import annotations

from datetime import datetime
from importlib import resources

import numpy as np

from ..types import Snapshot, Trajectory, VideoMetadata


class SqlTrajectoryRepository:
    """Implementa `TrajectoryRepository` sobre qualquer conexão DB-API (sqlite3
    local ou libsql/Turso)."""

    def __init__(self, connection) -> None:
        self._conn = connection

    # ---- setup -----------------------------------------------------------
    @staticmethod
    def _statements(sql: str) -> list[str]:
        """Quebra o schema em statements individuais (portável: nem todo cliente
        libsql expõe executescript; execute() de um statement por vez roda em
        ambos — sqlite3 local e Turso remoto)."""
        body = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
        return [s.strip() for s in body.split(";") if s.strip()]

    def init_schema(self) -> None:
        """Aplica o schema.sql (idempotente — tudo é CREATE TABLE IF NOT EXISTS)."""
        sql = resources.files("breakout.storage").joinpath("schema.sql").read_text(encoding="utf-8")
        for stmt in self._statements(sql):
            self._conn.execute(stmt)
        self._conn.commit()

    # ---- escrita (contrato) ---------------------------------------------
    def save_snapshot(self, snapshot: Snapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots (video_id, at, views, likes, comments) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                snapshot.video_id,
                snapshot.at.isoformat(),
                int(snapshot.views),
                int(snapshot.likes),
                int(snapshot.comments),
            ),
        )
        self._conn.commit()

    def save_metadata(self, metadata: VideoMetadata) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO videos "
            "(video_id, channel_id, title, duration_s, published_at, "
            " channel_subscribers, tags, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                metadata.video_id,
                metadata.channel_id,
                metadata.title,
                int(metadata.duration_s),
                metadata.published_at.isoformat(),
                int(metadata.channel_subscribers),
                ",".join(metadata.tags),
                metadata.category,
            ),
        )
        self._conn.commit()

    # ---- leitura (contrato) ---------------------------------------------
    def get_trajectory(self, video_id: str) -> Trajectory:
        rows = self._conn.execute(
            "SELECT at, views FROM snapshots WHERE video_id = ? ORDER BY at",
            (video_id,),
        ).fetchall()
        if not rows:
            raise KeyError(f"sem trajetória para {video_id!r}")

        times = [datetime.fromisoformat(r[0]) for r in rows]
        t0 = times[0]
        t = np.array([(ts - t0).total_seconds() / 3600.0 for ts in times], dtype=float)
        views = np.array([int(r[1]) for r in rows], dtype=np.int64)
        return Trajectory(video_id, t, views, self._load_metadata(video_id))

    def video_ids(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT video_id FROM snapshots").fetchall()
        return [r[0] for r in rows]

    # ---- interno ---------------------------------------------------------
    def _load_metadata(self, video_id: str) -> VideoMetadata | None:
        row = self._conn.execute(
            "SELECT video_id, channel_id, title, duration_s, published_at, "
            "       channel_subscribers, tags, category "
            "FROM videos WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if row is None:
            return None
        return VideoMetadata(
            video_id=row[0],
            channel_id=row[1] or "",
            title=row[2] or "",
            duration_s=int(row[3] or 0),
            published_at=datetime.fromisoformat(row[4]) if row[4] else datetime.min,
            channel_subscribers=int(row[5] or 0),
            tags=tuple(t for t in (row[6] or "").split(",") if t),
            category=row[7] or "unknown",
        )
