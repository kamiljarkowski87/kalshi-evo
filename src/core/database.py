"""Inicjalizacja i obsługa bazy SQLite."""
import sqlite3
from pathlib import Path
from src.core.logger import log


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).parent.parent.parent / "memory" / "schema.sql"
    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    log.info("database.initialized", path=db_path)


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
