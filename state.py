"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import asyncio
import sqlite3
import httpx
from fastapi import HTTPException

client: httpx.AsyncClient | None = None
write_conn: sqlite3.Connection | None = None
bearer_tokens: dict[str, tuple[str, float]] = {}
bearer_lock = asyncio.Lock()
domain_cache: dict = {"value": None, "expires": 0.0}
home_cache: dict = {}
stream_cache: dict = {}
walk_state: dict = {"running": False, "enriching": False}
background_task: asyncio.Task | None = None
probe_task: asyncio.Task | None = None


def require_client() -> httpx.AsyncClient:
    if client is None:
        raise HTTPException(status_code=503, detail="Server initializing, retry shortly")
    return client


def require_db() -> sqlite3.Connection:
    if write_conn is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return write_conn


def commit() -> None:
    if write_conn is not None:
        write_conn.commit()