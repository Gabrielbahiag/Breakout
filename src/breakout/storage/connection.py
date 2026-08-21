"""Fábrica de conexão — o único lugar que sabe se é SQLite local ou Turso.

Esta é a costura dev↔prod. Se houver credenciais de Turso nas settings, conecta
no Turso (libSQL); senão, abre um SQLite local em modo WAL. O repositório acima
não muda em nenhum dos casos — ele só recebe a conexão.
"""
from __future__ import annotations

from pathlib import Path

from ..settings import Settings


def make_connection(settings: Settings):
    """Devolve uma conexão DB-API. Turso se configurado, senão SQLite local WAL."""
    if settings.turso_database_url:
        # Turso/libSQL — o banco ATUAL. Conexão REMOTA PURA (HTTP): correta para
        # os runners efêmeros do GitHub Actions, que não têm arquivo local
        # persistente (por isso NÃO usamos embedded replica / sync).
        # O cliente expõe API estilo sqlite3 (.execute/.commit/.fetchall).
        # pip install libsql-experimental  (incluído no extra [prod])
        # A assinatura de connect() pode variar entre versões do SDK Python do
        # Turso (em transição); confira: https://docs.turso.tech/sdk/python
        import libsql_experimental as libsql  # type: ignore

        return libsql.connect(
            database=settings.turso_database_url,
            auth_token=settings.turso_auth_token or None,
        )

    # Desenvolvimento: SQLite local, WAL para leitura concorrente (dashboard).
    import sqlite3

    Path(settings.local_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.local_db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
