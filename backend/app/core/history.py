import json
import sqlite3
from datetime import datetime, timezone

from app.core.config import HISTORY_DB_PATH


def init_db() -> None:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources TEXT NOT NULL,
                grounded INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_turn(session_id: str, query: str, answer: str, sources: list[dict], grounded: bool) -> None:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    try:
        conn.execute(
            "INSERT INTO chat_history (session_id, query, answer, sources, grounded, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, query, answer, json.dumps(sources), int(grounded), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(session_id: str) -> list[dict]:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT query, answer, sources, grounded, created_at FROM chat_history WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "query": query,
            "answer": answer,
            "sources": json.loads(sources),
            "grounded": bool(grounded),
            "created_at": created_at,
        }
        for query, answer, sources, grounded, created_at in rows
    ]
