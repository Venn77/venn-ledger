import sqlite3
from typing import Any, Dict, List, Optional, cast
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from config import DB_PATH


def get_read_only_engine() -> Engine:
    """
    Creates a strictly read-only SQLAlchemy engine for SQLite.
    Adheres to the guardrail preventing destructive LLM queries.
    """
    def creator():
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    return create_engine("sqlite://", creator=creator, echo=False)

def execute_ro_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Executes a parameterized SQL query safely against the read-only engine."""
    engine = get_read_only_engine()

    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = [dict(row) for row in result.mappings()]
        return cast(List[Dict[str, Any]], rows)
