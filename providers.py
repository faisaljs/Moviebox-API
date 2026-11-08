import time
import asyncio
import httpx
from config import (
    KNOWN_HOSTS, DEFAULT_HEADERS, API_BASE,
    PROVIDER_PROBE_TIMEOUT, CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_SECONDS,
    PROVIDER_PROBE_INTERVAL,
)
import state


def _fresh_state(host: str) -> dict:
    return {
        "host": host,
        "alive": True,
        "consecutive_failures": 0,
        "total_success": 0,
        "total_failure": 0,
        "last_success": 0.0,
        "last_failure": 0.0,
        "last_error": None,
        "avg_latency_ms": 0.0,
        "circuit_open_until": 0.0,
    }


provider_state: dict = {host: _fresh_state(host) for host in KNOWN_HOSTS}


def mark_success(host: str, elapsed_ms: float):
    st = provider_state.get(host)
    if st is None:
        return
    if st["avg_latency_ms"] > 0:
        st["avg_latency_ms"] = 0.7 * st["avg_latency_ms"] + 0.3 * elapsed_ms
    else:
        st["avg_latency_ms"] = elapsed_ms
    st["alive"] = True
    st["consecutive_failures"] = 0
    st["last_success"] = time.time()
    st["circuit_open_until"] = 0
    st["total_success"] += 1
    st["last_error"] = None


def mark_failure(host: str, error: str):
    st = provider_state.get(host)
    if st is None:
        return
    st["consecutive_failures"] += 1
    st["last_failure"] = time.time()
    st["last_error"] = error[:200]
    st["total_failure"] += 1
    if st["consecutive_failures"] >= CIRCUIT_BREAKER_THRESHOLD:
        st["alive"] = False
        st["circuit_open_until"] = time.time() + CIRCUIT_BREAKER_SECONDS


def ordered_candidates(preferred: str | None, strict: bool) -> list[str]:
    now = time.time()
    if strict and preferred and preferred in provider_state:
        return [preferred]

    ordered: list[str] = []
    eligible = {
        h for h, st in provider_state.items()
        if st["circuit_open_until"] <= now
    }
    if preferred and preferred in eligible:
        ordered.append(preferred)

    healthy = [
        (st["avg_latency_ms"] or 9999, h)
        for h, st in provider_state.items()
        if h not in ordered and h in eligible and st["alive"]
    ]
    healthy.sort()
    ordered.extend(h for _, h in healthy)

    rest = [
        (st["avg_latency_ms"] or 9999, h)
        for h, st in provider_state.items()
        if h not in ordered and h in eligible
    ]
    rest.sort()
    ordered.extend(h for _, h in rest)

    if not ordered and provider_state:
        first = min(
            provider_state.items(),
            key=lambda item: (item[1]["circuit_open_until"], item[1]["avg_latency_ms"] or 9999),
        )[0]
        ordered.append(first)

    return ordered


async def probe_provider(host: str) -> dict:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROVIDER_PROBE_TIMEOUT) as c:
            resp = await c.get(
                f"{API_BASE}/home?host={host}",
                headers={
                    "User-Agent": DEFAULT_HEADERS["User-Agent"],
                    "Referer": DEFAULT_HEADERS["Referer"],
                },
            )
        elapsed_ms = (time.time() - start) * 1000
        if resp.status_code == 200:
            mark_success(host, elapsed_ms)
            return {"host": host, "alive": True, "latency_ms": int(elapsed_ms)}
        mark_failure(host, f"HTTP {resp.status_code}")
        return {"host": host, "alive": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        mark_failure(host, str(e))
        return {"host": host, "alive": False, "error": str(e)[:120]}


async def probe_loop():
    await asyncio.sleep(5)
    idx = 0
    while True:
        try:
            if idx >= len(KNOWN_HOSTS):
                idx = 0
            await probe_provider(KNOWN_HOSTS[idx])
            idx += 1
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"probe loop: {e}")
        await asyncio.sleep(PROVIDER_PROBE_INTERVAL)