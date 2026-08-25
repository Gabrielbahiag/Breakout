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
    # check_same_thread=False: o dashboard guarda esta conexão num
    # st.cache_resource (um objeto só, reusado entre reruns) — o Streamlit
    # executa reruns em threads variadas, e o sqlite3 por padrão proíbe usar
    # a mesma conexão fora da thread que a criou. Seguro aqui porque o
    # dashboard é read-only (nunca escreve) e cada rerun é sequencial, não
    # concorrente de verdade.
    conn = sqlite3.connect(settings.local_db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
