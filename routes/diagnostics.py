import json
import time
from fastapi import APIRouter, HTTPException, Query
import state
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


@router.get("/debug/tokens")
async def debug_tokens():
    now = time.time()
    return {
        "count": len(state.bearer_tokens),
        "tokens": {
            host: {
                "length": len(token),
                "preview": token[:24] + "..." if len(token) > 24 else token,
                "age_seconds": int(now - ts),
            }
            for host, (token, ts) in state.bearer_tokens.items()
        },
        "domain_cache": {
            "value": state.domain_cache["value"],
            "expires_in": max(0, int(state.domain_cache["expires"] - now)),
        },
    }


@router.post("/debug/fetch-token")
async def debug_fetch_token(host: str = DEFAULT_HOST):
    token = await upstream._fetch_token(host)
    return {
        "host": host,
        "success": bool(token),
        "length": len(token),
        "preview": (token[:24] + "...") if token else None,
    }


@router.post("/debug/play")
async def debug_play(subject_id: str, detail_path: str, se: int = 0, ep: int = 0):
    try:
        domain = await upstream.get_player_domain()
        result = await upstream._play_attempt(domain, subject_id, detail_path, se, ep)
        data = result["data"]
        return {
            "domain": domain,
            "referer": result["referer"],
            "hasResource": data.get("hasResource"),
            "streams": len(data.get("streams", []) or []),
            "freeNum": data.get("freeNum"),
            "raw_keys": list(data.keys()),
        }
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)[:300]}


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
    }