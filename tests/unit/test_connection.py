"""Testes da fábrica de conexão (connection.py).

O teste-chave é uma regressão de bug real: o dashboard guarda a conexão
SQLite local num `st.cache_resource` (um objeto só, reusado entre reruns do
Streamlit) — e o Streamlit executa reruns em threads variadas. `sqlite3` por
padrão proíbe usar a mesma conexão fora da thread que a criou
(`check_same_thread=True`), o que derrubava o dashboard com
"SQLite objects created in a thread can only be used in that same thread".
"""
from __future__ import annotations

import threading

import pytest

from breakout.settings import Settings
from breakout.storage.connection import make_connection

pytestmark = pytest.mark.unit


def _local_settings(tmp_path) -> Settings:
    # turso_database_url="" força o fallback SQLite mesmo se o .env local
    # tiver credenciais reais configuradas (Settings lê de .env por padrão).
    return Settings(
        local_db_path=str(tmp_path / "test.db"),
        turso_database_url="",
        turso_auth_token="",
    )


def test_conexao_sqlite_local_funciona_fora_da_thread_que_criou(tmp_path):
    conn = make_connection(_local_settings(tmp_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()

    outcome: dict[str, object] = {}

    def _query_from_other_thread() -> None:
        try:
            conn.execute("SELECT * FROM t").fetchall()
            outcome["ok"] = True
        except Exception as e:  # noqa: BLE001 — queremos capturar pra afirmar abaixo
            outcome["error"] = e

    thread = threading.Thread(target=_query_from_other_thread)
    thread.start()
    thread.join()

    assert outcome.get("ok") is True, outcome.get("error")


def test_conexao_sqlite_local_cria_arquivo_com_wal(tmp_path):
    conn = make_connection(_local_settings(tmp_path))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
