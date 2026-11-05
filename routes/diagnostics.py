"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import json
import time
from fastapi import APIRouter, HTTPException, Query
import state
import storage
import providers
import upstream
from config import (
    API_VERSION, DEFAULT_HOST, KNOWN_HOSTS, API_BASE, DEFAULT_HEADERS,
    TAB_PAYLOAD_VARIANTS,
)

router = APIRouter()


@router.get("/api/tabs")
async def discover_tabs(
    min_id: int = Query(default=1, ge=1),
    max_id: int = Query(default=20, ge=1),
    per_page: int = Query(default=3, ge=1, le=20),
):
    if max_id < min_id:
        raise HTTPException(400, detail="max_id must be greater than or equal to min_id")
    if max_id - min_id + 1 > 50:
        raise HTTPException(400, detail="A maximum of 50 tab IDs can be probed per request")
    results = []
    for tab_id in range(min_id, max_id + 1):
        payload = {"tabId": tab_id, "page": 1, "perPage": per_page,
                   **TAB_PAYLOAD_VARIANTS["baseline"]}
        try:
            data = await upstream.bff_request("/subject/filter", method="POST", payload=payload)
            inner = data.get("data", {}) or {}
            raw = inner.get("items") or inner.get("subjects") or []
            pager = inner.get("pager") or {}
            total = pager.get("totalCount")
            results.append({
                "tab_id": tab_id,
                "count": len(raw),
                "pager_total": total,
                "sentinel": bool((total or 0) >= 1000000),
                "sample_titles": [s.get("title") for s in raw if s.get("title")][:3],
            })
        except Exception as e:
            results.append({"tab_id": tab_id, "error": str(e)})
    return {"variant": "baseline", "results": results}


@router.get("/api/tabs/variants")
async def discover_tab_variants(tab_id: int = 2, per_page: int = 3):
    out = []
    for name, body in TAB_PAYLOAD_VARIANTS.items():
        payload = {"tabId": tab_id, "page": 1, "perPage": per_page}
        if body is not None:
            payload.update(body)
        try:
            data = await upstream.bff_request("/subject/filter", method="POST", payload=payload)
            inner = data.get("data", {}) or {}
            raw = inner.get("items") or inner.get("subjects") or []
            pager = inner.get("pager") or {}
            total = pager.get("totalCount")
            out.append({
                "variant": name, "payload": body, "count": len(raw),
                "pager_total": total, "sentinel": bool((total or 0) >= 1000000),
                "sample_titles": [s.get("title") for s in raw if s.get("title")][:3],
            })
        except Exception as e:
            out.append({"variant": name, "error": str(e)})
    breaking = [v for v in out if not v.get("sentinel") and not v.get("error")]
    return {
        "tab_id": tab_id,
        "variants": out,
        "non_sentinel_variants": [v["variant"] for v in breaking],
        "hint": (
            "If non_sentinel_variants is non-empty, that payload shape works."
        ) if breaking else (
            "All variants sentinel. /subject/filter requires auth we don't have as guest."
        ),
    }


@router.get("/api/debug/upstream")
async def debug_upstream(path: str, method: str = "GET", payload: str | None = None):
    if not path.startswith("/"):
        path = "/" + path
    body = json.loads(payload) if payload else None
    client = state.require_client()
    token = await upstream.get_bearer_token(DEFAULT_HOST)
    headers = {**DEFAULT_HEADERS}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if method == "POST":
            resp = await client.post(f"{API_BASE}{path}", headers=headers, json=body)
        else:
            resp = await client.get(f"{API_BASE}{path}", headers=headers)
        return resp.json()
    except Exception as e:
        raise HTTPException(502, detail=f"debug upstream failed: {e}")


@router.get("/health")
async def health():
    now = time.time()
    providers_health = {
        h: {
            "alive": st["alive"],
            "latency_ms": int(st["avg_latency_ms"]),
            "fails": st["consecutive_failures"],
            "circuit_open": st["circuit_open_until"] > now,
        }
        for h, st in providers.provider_state.items()
    }
    pool = state.client._transport._pool if state.client is not None else None
    return {
        "status": "ok",
        "version": API_VERSION,
        "default_host": DEFAULT_HOST,
        "known_hosts": KNOWN_HOSTS,
        "providers": providers_health,
        "tokens_cached": len(state.bearer_tokens),
        "domain_cached": state.domain_cache["value"],
        "domain_expires_in": max(0, int(state.domain_cache["expires"] - now)),
        "stream_cache_size": len(state.stream_cache),
        "home_cache_size": len(state.home_cache),
        "client_pool_connections": len(pool.connections) if pool is not None else None,
        "catalog_indexed": storage.read_scalar("SELECT COUNT(*) FROM subjects") or 0,
        "walk_running": state.walk_state.get("running", False),
        "enriching": state.walk_state.get("enriching", False),
    }
