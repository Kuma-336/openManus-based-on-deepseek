import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from app.logger import logger
from app.schema import Message


DB_PATH = Path(__file__).parent.parent.parent / "workspace" / "memory.db"
SEARCH_CACHE_TTL_HOURS = 24


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT,
                tool_calls  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_session ON task_history(session_id);

            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash   TEXT PRIMARY KEY,
                query        TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                expires_at   TEXT NOT NULL
            );
        """)


_init_db()


class PersistentMemory:
    # ── 会话历史 ──────────────────────────────────────────────

    @staticmethod
    def save_messages(session_id: str, messages: List[Message]) -> None:
        """追加写入新增消息（跳过已持久化的部分）。"""
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM task_history WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            new_msgs = messages[existing:]
            if not new_msgs:
                return
            ts = datetime.now().isoformat()
            conn.executemany(
                "INSERT INTO task_history(session_id, timestamp, role, content, tool_calls)"
                " VALUES(?,?,?,?,?)",
                [
                    (
                        session_id,
                        ts,
                        m.role,
                        m.content,
                        json.dumps(
                            [tc.model_dump() for tc in m.tool_calls]
                            if m.tool_calls
                            else None
                        ),
                    )
                    for m in new_msgs
                ],
            )
        logger.debug(f"[memory] 已保存 {len(new_msgs)} 条消息，session={session_id}")

    @staticmethod
    def load_session(session_id: str) -> List[Message]:
        """加载指定会话的全部消息。"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content, tool_calls FROM task_history"
                " WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        messages = []
        for row in rows:
            raw_tc = row["tool_calls"]
            tool_calls = (
                json.loads(raw_tc)
                if raw_tc and raw_tc != "null"
                else None
            )
            messages.append(
                Message(role=row["role"], content=row["content"], tool_calls=tool_calls)
            )
        return messages

    @staticmethod
    def list_sessions(limit: int = 10) -> List[dict]:
        """返回最近 N 个会话的摘要。"""
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT session_id,
                       MIN(timestamp) AS started_at,
                       COUNT(*)       AS msg_count
                FROM task_history
                GROUP BY session_id
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            result = []
            for row in rows:
                first_user = conn.execute(
                    "SELECT content FROM task_history"
                    " WHERE session_id=? AND role='user' ORDER BY id LIMIT 1",
                    (row["session_id"],),
                ).fetchone()
                preview = (first_user["content"] or "")[:60] if first_user else ""
                result.append(
                    {
                        "session_id": row["session_id"],
                        "started_at": row["started_at"],
                        "msg_count": row["msg_count"],
                        "preview": preview,
                    }
                )
        return result

    # ── 搜索缓存 ──────────────────────────────────────────────

    @staticmethod
    def _query_hash(query: str, num_results: int) -> str:
        return hashlib.sha256(f"{query}|{num_results}".encode()).hexdigest()

    @staticmethod
    def get_search_cache(query: str, num_results: int) -> Optional[list]:
        """返回未过期的缓存结果，未命中返回 None。"""
        key = PersistentMemory._query_hash(query, num_results)
        now = datetime.now().isoformat()
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT results_json FROM search_cache"
                " WHERE query_hash=? AND expires_at > ?",
                (key, now),
            ).fetchone()
        if row:
            logger.info(f"[search cache] 命中缓存: {query!r}")
            return json.loads(row["results_json"])
        return None

    @staticmethod
    def set_search_cache(
        query: str,
        num_results: int,
        results: list,
        ttl_hours: int = SEARCH_CACHE_TTL_HOURS,
    ) -> None:
        """写入搜索结果缓存。"""
        key = PersistentMemory._query_hash(query, num_results)
        now = datetime.now()
        expires = (now + timedelta(hours=ttl_hours)).isoformat()
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO search_cache"
                "(query_hash, query, results_json, created_at, expires_at)"
                " VALUES(?,?,?,?,?)",
                (key, query, json.dumps(results), now.isoformat(), expires),
            )
        logger.debug(f"[search cache] 已缓存: {query!r}，TTL={ttl_hours}h")
