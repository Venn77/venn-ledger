import sqlite3
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

def execute_ro_query(query: str) -> list[dict]:
    """
    Executes a raw SQL string against the read-only engine safely.
    Returns results as a list of dictionaries.
    """
    engine = get_read_only_engine()

    with engine.connect() as conn:
        result = conn.execute(text(query))
        # noinspection PyProtectedMember
        return [dict(row._mapping) for row in result]


