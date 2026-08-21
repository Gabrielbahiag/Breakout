"""Testes da política de cadência (a lógica que substitui o APScheduler).

Verifica que a seleção "quem está vencido" respeita intervalos diferentes para
vídeo quente e frio, e que a aposentadoria tira vídeos velhos da carteira.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from breakout.collect import policy
from breakout.settings import Settings
from breakout.storage.sql_repository import SqlTrajectoryRepository

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def _db():
    conn = sqlite3.connect(":memory:")
    SqlTrajectoryRepository(conn).init_schema()
    return conn


def _add_video(conn, vid, published_h_ago=None, sampled_h_ago=None, active=1):
    published = (NOW - timedelta(hours=published_h_ago)).isoformat() if published_h_ago is not None else None
    sampled = (NOW - timedelta(hours=sampled_h_ago)).isoformat() if sampled_h_ago is not None else None
    conn.execute(
        "INSERT INTO videos (video_id, published_at, last_sampled_at, active) VALUES (?, ?, ?, ?)",
        (vid, published, sampled, active),
    )
    conn.commit()


def test_nunca_amostrado_esta_vencido():
    conn = _db()
    _add_video(conn, "novo", published_h_ago=1, sampled_h_ago=None)
    assert "novo" in policy.select_due(conn, NOW, Settings())


def test_quente_usa_intervalo_curto():
    conn = _db()
    s = Settings(hot_interval_h=1.0, cold_interval_h=6.0, hot_age_h=24.0)
    # jovem (2h), amostrado há 2h => vencido no intervalo quente (1h)
    _add_video(conn, "quente", published_h_ago=2, sampled_h_ago=2)
    assert "quente" in policy.select_due(conn, NOW, s)


def test_frio_nao_vence_no_intervalo_curto():
    conn = _db()
    s = Settings(hot_interval_h=1.0, cold_interval_h=6.0, hot_age_h=24.0)
    # velho (48h => frio), amostrado há 2h => NÃO vencido (frio espera 6h)
    _add_video(conn, "frio", published_h_ago=48, sampled_h_ago=2)
    assert "frio" not in policy.select_due(conn, NOW, s)


def test_inativo_fica_de_fora():
    conn = _db()
    _add_video(conn, "aposentado", published_h_ago=1, sampled_h_ago=None, active=0)
    assert "aposentado" not in policy.select_due(conn, NOW, Settings())


def test_retire_stale_aposenta_velhos():
    conn = _db()
    s = Settings(retire_after_h=168.0)  # 7 dias
    _add_video(conn, "velho", published_h_ago=200)   # > 7 dias
    _add_video(conn, "recente", published_h_ago=10)
    policy.retire_stale(conn, NOW, s)
    ativos = {r[0] for r in conn.execute("SELECT video_id FROM videos WHERE active = 1").fetchall()}
    assert ativos == {"recente"}
