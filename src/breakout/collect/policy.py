"""Política de cadência — a inteligência que substitui o APScheduler.

Em vez de um agendador em processo, a cadência adaptativa vira uma decisão SEM
ESTADO: a cada execução (chamada pelo GitHub Actions), consultamos a carteira no
banco e perguntamos "quem está vencido pra amostrar agora?". Vídeo jovem/quente
tem intervalo curto (resolução fina na fase de decolagem); vídeo frio, intervalo
longo; vídeo velho demais é aposentado. Todo o estado vive no banco — perfeito
pra runners efêmeros.
"""
from __future__ import annotations

from datetime import datetime

from ..settings import Settings


def _hours_between(a_iso: str | None, now: datetime) -> float | None:
    if not a_iso:
        return None
    return (now - datetime.fromisoformat(a_iso)).total_seconds() / 3600.0


def select_due(conn, now: datetime, settings: Settings) -> list[str]:
    """IDs de vídeos ativos que estão vencidos para uma nova amostragem."""
    rows = conn.execute(
        "SELECT video_id, published_at, last_sampled_at FROM videos WHERE active = 1"
    ).fetchall()

    due: list[str] = []
    for video_id, published_at, last_sampled_at in rows:
        age_h = _hours_between(published_at, now)
        interval = (
            settings.hot_interval_h
            if age_h is None or age_h <= settings.hot_age_h
            else settings.cold_interval_h
        )
        gap_h = _hours_between(last_sampled_at, now)
        if gap_h is None or gap_h >= interval:   # nunca amostrado, ou vencido
            due.append(video_id)
    return due


def mark_sampled(conn, video_ids: list[str], now: datetime) -> None:
    ts = now.isoformat()
    conn.executemany(
        "UPDATE videos SET last_sampled_at = ? WHERE video_id = ?",
        [(ts, v) for v in video_ids],
    )
    conn.commit()


def retire_stale(conn, now: datetime, settings: Settings) -> int:
    """Aposenta da carteira vídeos velhos demais (para de gastar cota neles)."""
    cur = conn.execute(
        "UPDATE videos SET active = 0 "
        "WHERE active = 1 AND published_at IS NOT NULL "
        "AND (julianday(?) - julianday(published_at)) * 24.0 > ?",
        (now.isoformat(), settings.retire_after_h),
    )
    conn.commit()
    return cur.rowcount if cur.rowcount is not None else 0
