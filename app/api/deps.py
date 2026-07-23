import sqlite3
from typing import Iterator

from app.config import get_config
from app.database import get_connection


def get_db() -> Iterator[sqlite3.Connection]:
    """Uma conexão SQLite nova por request (mesmo padrão de "conexão por
    chamada" já usado no watcher), fechada ao final. WAL + busy_timeout
    (configurados em get_connection/init_db) absorvem a concorrência com o
    watcher escrevendo em paralelo."""
    config = get_config()
    conn = get_connection(config.db_path, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()
