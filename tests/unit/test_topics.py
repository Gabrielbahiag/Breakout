"""Testes de discover_topics (topics.py) — a lista de nichos/idiomas do
discover automático, editável pelo dashboard (Fase 7).

Estilo "engenharia" (Seção 9 do CLAUDE.md): mock/estado determinístico,
`assert x == y`. Usa sqlite3 `:memory:` com o schema aplicado, mesmo padrão
de test_sql_repository.py.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from breakout.collect import topics
from breakout.storage.sql_repository import SqlTrajectoryRepository

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SqlTrajectoryRepository(c).init_schema()
    return c


def test_lista_vazia_quando_nao_ha_topicos(conn):
    assert topics.list_topics(conn) == []


def test_add_e_list_topics_roundtrip(conn):
    topics.add_topic(conn, "valorant", "pt", now=NOW)
    topics.add_topic(conn, "minecraft shorts", "en", now=NOW)
    got = topics.list_topics(conn)
    assert [(t.query, t.language) for t in got] == [("valorant", "pt"), ("minecraft shorts", "en")]
    assert all(t.active for t in got)


def test_add_topic_sem_idioma():
    conn = sqlite3.connect(":memory:")
    SqlTrajectoryRepository(conn).init_schema()
    topics.add_topic(conn, "valorant", None, now=NOW)
    got = topics.list_topics(conn)
    assert got[0].language is None


def test_add_topic_query_vazia_levanta(conn):
    with pytest.raises(ValueError):
        topics.add_topic(conn, "", "pt", now=NOW)
    with pytest.raises(ValueError):
        topics.add_topic(conn, "   ", "pt", now=NOW)


def test_add_topic_tira_espacos_nas_bordas(conn):
    topics.add_topic(conn, "  valorant  ", "pt", now=NOW)
    assert topics.list_topics(conn)[0].query == "valorant"


def test_remove_topic(conn):
    topics.add_topic(conn, "valorant", "pt", now=NOW)
    topic_id = topics.list_topics(conn)[0].id
    topics.remove_topic(conn, topic_id)
    assert topics.list_topics(conn) == []


def test_set_active_false_esconde_de_list_topics_por_padrao(conn):
    topics.add_topic(conn, "valorant", "pt", now=NOW)
    topic_id = topics.list_topics(conn)[0].id
    topics.set_active(conn, topic_id, False)
    assert topics.list_topics(conn) == []
    assert topics.list_topics(conn, only_active=False)[0].active is False


def test_set_active_true_reativa(conn):
    topics.add_topic(conn, "valorant", "pt", now=NOW)
    topic_id = topics.list_topics(conn)[0].id
    topics.set_active(conn, topic_id, False)
    topics.set_active(conn, topic_id, True)
    assert len(topics.list_topics(conn)) == 1
