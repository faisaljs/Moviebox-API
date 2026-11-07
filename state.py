import asyncio
import httpx
from fastapi import HTTPException

client: httpx.AsyncClient | None = None
bearer_tokens: dict[str, tuple[str, float]] = {}
bearer_lock = asyncio.Lock()
domain_cache: dict = {"value": None, "expires": 0.0}
home_cache: dict = {}
stream_cache: dict = {}
probe_task: asyncio.Task | None = None


def require_client() -> httpx.AsyncClient:
    if client is None:
        raise HTTPException(status_code=503, detail="Server initializing, retry shortly")
    return client