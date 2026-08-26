"""Nichos/idiomas do discover automático (Fase 7) — configuração operacional
de PRODUTO, não dado coletado. Opera direto sobre a conexão (mesmo estilo de
`collect/policy.py`), fora do contrato `TrajectoryRepository` — não é sobre
trajetórias, é uma tabela de preferência à parte (`discover_topics`).

Editável pelo dashboard: é a ÚNICA tabela que o dashboard tem permissão de
escrever (exceção documentada ao "dashboard read-only" — Seção 5 do
CLAUDE.md). Trocar de nicho não arrisca corromper o núcleo append-only
sagrado (videos/snapshots) porque não é dado colhido, é preferência.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Topic:
    """Um nicho configurado pro discover automático rastrear."""

    id: int
    query: str
    language: str | None
    active: bool


def list_topics(conn, *, only_active: bool = True) -> list[Topic]:
    """Nichos configurados, na ordem em que foram adicionados. `only_active`
    (padrão) esconde os pausados via `set_active(..., False)`."""
    sql = "SELECT id, query, language, active FROM discover_topics"
    if only_active:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    rows = conn.execute(sql).fetchall()
    return [Topic(id=r[0], query=r[1], language=r[2], active=bool(r[3])) for r in rows]


def add_topic(conn, query: str, language: str | None, *, now: datetime) -> None:
    """Adiciona um nicho. `query` vazia (ou só espaço) é erro — não faz
    sentido rastrear 'nada', e um discover com termo vazio devolveria
    resultado inesperado da API."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query não pode ser vazia")
    conn.execute(
        "INSERT INTO discover_topics (query, language, active, created_at) VALUES (?, ?, 1, ?)",
        (query, language or None, now.isoformat()),
    )
    conn.commit()


def remove_topic(conn, topic_id: int) -> None:
    """Remove um nicho de vez (diferente de pausar via `set_active`)."""
    conn.execute("DELETE FROM discover_topics WHERE id = ?", (topic_id,))
    conn.commit()


def set_active(conn, topic_id: int, active: bool) -> None:
    """Pausa/reativa um nicho sem apagar (histórico de configuração
    preservado — útil pra "desligar por um tempo" sem perder o termo)."""
    conn.execute("UPDATE discover_topics SET active = ? WHERE id = ?", (int(active), topic_id))
    conn.commit()
