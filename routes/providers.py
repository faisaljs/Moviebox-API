import time
import asyncio
from fastapi import APIRouter
import providers as provider_registry
from config import (
    DEFAULT_HOST, KNOWN_HOSTS,
    CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_SECONDS,
)

router = APIRouter()


@router.get("/providers")
async def list_providers():
    now = time.time()
    entries = []
    for host, st in provider_registry.provider_state.items():
        entries.append({
            "host": host,
            "alive": st["alive"],
            "circuit_open": st["circuit_open_until"] > now,
            "circuit_open_for": max(0, int(st["circuit_open_until"] - now)),
            "consecutive_failures": st["consecutive_failures"],
            "total_success": st["total_success"],
            "total_failure": st["total_failure"],
            "avg_latency_ms": int(st["avg_latency_ms"]),
            "last_success_ago": max(0, int(now - st["last_success"])) if st["last_success"] else None,
            "last_failure_ago": max(0, int(now - st["last_failure"])) if st["last_failure"] else None,
            "last_error": st["last_error"],
        })
    entries.sort(key=lambda p: KNOWN_HOSTS.index(p["host"]) if p["host"] in KNOWN_HOSTS else 999)
    return {
        "default_host": DEFAULT_HOST,
        "provider_count": len(entries),
        "healthy": sum(1 for p in entries if p["alive"] and not p["circuit_open"]),
        "degraded": sum(1 for p in entries if p["circuit_open"]),
        "providers": entries,
        "circuit_breaker": {
            "threshold": CIRCUIT_BREAKER_THRESHOLD,
            "window_seconds": CIRCUIT_BREAKER_SECONDS,
        },
    }


@router.post("/providers/probe")
async def probe_providers():
    results = await asyncio.gather(
        *(provider_registry.probe_provider(h) for h in KNOWN_HOSTS)
    )
    return {"probed": len(results), "results": results}


@router.post("/providers/reset")
async def reset_providers():
    for st in provider_registry.provider_state.values():
        st["alive"] = True
        st["consecutive_failures"] = 0
        st["circuit_open_until"] = 0
        st["last_error"] = None
    return {"status": "reset", "providers": len(provider_registry.provider_state)}


@router.get("/api/hosts")
async def legacy_hosts(refresh: bool = False):
    data = await list_providers()
    return {
        "primary": data["default_host"],
        "known_hosts": KNOWN_HOSTS,
        "results": [
            {"host": p["host"], "alive": p["alive"], "latency_ms": p["avg_latency_ms"]}
            for p in data["providers"]
        ],
        "unique_catalogs": 1,
    }