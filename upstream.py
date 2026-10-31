"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import re
import json
import time
import asyncio
import httpx
from fastapi import HTTPException
from config import (
    API_BASE, DEFAULT_HOST, DEFAULT_HEADERS, PLAYER_HEADERS,
    DOMAIN_TTL, RETRY_BACKOFF, PROVIDER_PROBE_TIMEOUT,
)
import state
import providers


STREAM_CACHE_TTL = 30.0


class _ProviderError(Exception):
    """Internal: a single provider attempt failed. bff_request handles retry/rotation."""


# ─── URL HELPERS ─────────────────────────────────────────────────────────────

def _add_host_param(path: str, host: str) -> str:
    if "?" in path:
        base, query = path.split("?", 1)
        params = [p for p in query.split("&") if p and not p.startswith("host=")]
        return f"{base}?{'&'.join(params)}&host={host}" if params else f"{base}?host={host}"
    return f"{path}?host={host}"


# ─── TOKEN MANAGEMENT ────────────────────────────────────────────────────────

async def _fetch_token(host: str) -> str:
    """Hit /home once, harvest token from x-user header or set-cookie."""
    client = state.require_client()
    try:
        resp = await client.get(
            f"{API_BASE}/home?host={host}",
            headers=DEFAULT_HEADERS,
            timeout=PROVIDER_PROBE_TIMEOUT,
        )
    except Exception:
        return ""

    x_user = resp.headers.get("x-user")
    if x_user:
        try:
            token = json.loads(x_user).get("token")
            if token:
                state.bearer_tokens[host] = (token, time.time())
                return token
        except json.JSONDecodeError:
            pass

    cookie = resp.headers.get("set-cookie", "")
    m = re.search(r"token=([^;]+)", cookie)
    if m:
        state.bearer_tokens[host] = (m.group(1), time.time())
        return m.group(1)
    return ""


async def get_bearer_token(host: str) -> str:
    cached = state.bearer_tokens.get(host)
    if cached:
        return cached[0]
    async with state.bearer_lock:
        cached = state.bearer_tokens.get(host)
        if cached:
            return cached[0]
        return await _fetch_token(host)


def _capture_rotated_token(host: str, resp: httpx.Response) -> str | None:
    x_user = resp.headers.get("x-user")
    if not x_user:
        return None
    try:
        token = json.loads(x_user).get("token")
        if token:
            state.bearer_tokens[host] = (token, time.time())
            return token
    except json.JSONDecodeError:
        pass
    return None


# ─── ONE PROVIDER ATTEMPT ────────────────────────────────────────────────────

async def _request_once(
    url: str, method: str, payload: dict | None, headers: dict,
) -> httpx.Response:
    client = state.require_client()
    try:
        if method == "POST":
            return await client.post(url, headers=headers, json=payload)
        return await client.get(url, headers=headers)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
        raise _ProviderError(type(e).__name__) from e


async def _attempt(
    host: str, path: str, method: str, payload: dict | None,
) -> tuple[dict, float]:
    """Single provider attempt. Raises _ProviderError on any failure."""
    token = await get_bearer_token(host)
    headers = {**DEFAULT_HEADERS}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{_add_host_param(path, host)}"
    start = time.time()

    resp = await _request_once(url, method, payload, headers)
    if (rotated := _capture_rotated_token(host, resp)):
        headers["Authorization"] = f"Bearer {rotated}"

    if resp.status_code == 401:
        state.bearer_tokens.pop(host, None)
        token = await get_bearer_token(host)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            resp = await _request_once(url, method, payload, headers)
            _capture_rotated_token(host, resp)

    if resp.status_code == 429:
        ra = resp.headers.get("retry-after")
        delay = float(ra) if ra and ra.isdigit() else RETRY_BACKOFF
        await asyncio.sleep(min(delay, 5.0))
        resp = await _request_once(url, method, payload, headers)

    if resp.status_code != 200:
        raise _ProviderError(f"HTTP {resp.status_code}")

    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        raise _ProviderError("non-JSON response") from e

    return data, (time.time() - start) * 1000


async def bff_request(
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    preferred_host: str | None = None,
    strict_host: bool = False,
) -> dict:
    candidates = providers.ordered_candidates(preferred_host, strict_host)
    if not candidates:
        raise HTTPException(503, detail="No providers available")

    last_error: str | None = None
    for host in candidates:
        try:
            data, elapsed_ms = await _attempt(host, path, method, payload)
        except _ProviderError as e:
            providers.mark_failure(host, str(e))
            last_error = f"{host}: {e}"
            if strict_host and host == preferred_host:
                break
            continue
        providers.mark_success(host, elapsed_ms)
        return data

    raise HTTPException(
        status_code=502,
        detail=f"All {len(candidates)} providers failed. Last: {last_error}",
    )


# ─── PLAYER DOMAIN ───────────────────────────────────────────────────────────

async def get_player_domain(force_refresh: bool = False) -> str:
    now = time.time()
    if not force_refresh and state.domain_cache["value"] and now < state.domain_cache["expires"]:
        return state.domain_cache["value"]
    data = await bff_request("/media-player/get-domain")
    domain = (data.get("data") or "https://netfilm.world").rstrip("/")
    state.domain_cache["value"] = domain
    state.domain_cache["expires"] = now + DOMAIN_TTL
    return domain


def build_player_referer(domain: str, detail_path: str, subject_id: str, se: int, ep: int) -> str:
    return (
        f"{domain}/spa/videoPlayPage/movies/{detail_path}"
        f"?id={subject_id}&type=/movie/detail&detailSe={se}&detailEp={ep}&lang=en"
    )


# ─── STREAM RESOLUTION ───────────────────────────────────────────────────────

async def _play_attempt(domain: str, subject_id: str, detail_path: str, se: int, ep: int) -> dict:
    client = state.require_client()
    referer = build_player_referer(domain, detail_path, subject_id, se, ep)
    url = (
        f"{domain}/wefeed-h5api-bff/subject/play"
        f"?subjectId={subject_id}&se={se}&ep={ep}&detailPath={detail_path}"
    )
    resp = await client.get(url, headers={**PLAYER_HEADERS, "Referer": referer})
    if resp.status_code != 200:
        raise HTTPException(502, f"player HTTP {resp.status_code}")
    try:
        data = resp.json().get("data", {}) or {}
    except Exception:
        raise HTTPException(502, "player non-JSON")
    return {"domain": domain, "referer": referer, "data": data, "se": se, "ep": ep}


async def _resolve_stream_uncached(
    subject_id: str, detail_path: str, se: int, ep: int,
) -> dict:
    last_error = "unknown"
    for attempt in range(2):
        try:
            domain = await get_player_domain(force_refresh=(attempt > 0))
            result = await _play_attempt(domain, subject_id, detail_path, se, ep)

            # Movie fallback: no resource at (se, ep), retry as (0, 0).
            # Return truthful resolved_se/resolved_ep so the route can be honest
            # with the client about which episode actually played.
            if not result["data"].get("hasResource") and (se != 0 or ep != 0):
                try:
                    movie = await _play_attempt(domain, subject_id, detail_path, 0, 0)
                    if movie["data"].get("hasResource"):
                        movie["resolved_se"] = 0
                        movie["resolved_ep"] = 0
                        return movie
                except HTTPException:
                    pass

            result["resolved_se"] = se
            result["resolved_ep"] = ep
            return result
        except HTTPException as e:
            last_error = str(e.detail)
            if attempt == 0:
                continue
            raise
        except Exception as e:
            last_error = str(e)
            if attempt == 0:
                continue

    raise HTTPException(502, f"Stream resolution failed: {last_error}")


async def resolve_stream(subject_id: str, detail_path: str, se: int, ep: int) -> dict:
    """Memoized for STREAM_CACHE_TTL seconds. Collapses the 3x /play
    burst (sources + captions + proxy) into one upstream hit."""
    key = (subject_id, detail_path, se, ep)
    now = time.time()

    hit = state.stream_cache.get(key)
    if hit and now < hit[1]:
        return hit[0]

    # evict stale entries on access — cache stays bounded to the recent burst window
    if len(state.stream_cache) > 64:
        stale = [k for k, v in state.stream_cache.items() if v[1] <= now]
        for k in stale:
            state.stream_cache.pop(k, None)

    result = await _resolve_stream_uncached(subject_id, detail_path, se, ep)
    state.stream_cache[key] = (result, now + STREAM_CACHE_TTL)
    return result


async def resolve_captions(subject_id: str, detail_path: str, se: int, ep: int) -> list:
    stream = await resolve_stream(subject_id, detail_path, se, ep)
    data = stream["data"]
    streams = data.get("streams") or []
    dash = data.get("dash") or []

    stream_id = None
    stream_format = None
    if streams:
        stream_id = streams[0].get("id")
        stream_format = streams[0].get("format", "MP4")
    elif dash:
        stream_id = dash[0].get("id")
        stream_format = dash[0].get("format", "DASH")

    if not stream_id:
        return []

    cap_path = (
        f"/subject/caption?format={stream_format}&id={stream_id}"
        f"&subjectId={subject_id}&detailPath={detail_path}"
    )
    data = await bff_request(cap_path)
    inner = data.get("data", {}) or {}
    return inner.get("captions", []) if isinstance(inner, dict) else inner
