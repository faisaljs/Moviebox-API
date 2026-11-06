"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import os
import sqlite3
import asyncio
import base64
import binascii
import hmac
import time
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import state
import storage
import providers
import catalog_worker
from config import (
    API_VERSION, PORT, BIND_HOST, CORS_ORIGINS, REQUEST_TIMEOUT, CATALOG_DB, STATIC_DIR,
    AUTH_ENABLED, AUTH_USER, AUTH_PASSWORD, RATE_LIMIT_PER_MINUTE,
    EXPENSIVE_RATE_LIMIT_PER_MINUTE,
)
from dashboard import DASHBOARD_HTML
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=10.0),
        limits=httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=30.0,
        ),
        follow_redirects=True,
    )
    os.makedirs(os.path.dirname(os.path.abspath(CATALOG_DB)), exist_ok=True)
    state.write_conn = sqlite3.connect(
        CATALOG_DB, timeout=30.0, check_same_thread=False,
    )
    state.write_conn.execute("PRAGMA busy_timeout=30000")
    state.write_conn.execute("PRAGMA foreign_keys=ON")
    state.write_conn.execute("PRAGMA journal_mode=WAL")
    state.write_conn.execute("PRAGMA synchronous=NORMAL")
    storage.init_schema()

    # Refuse to start on a corrupt DB — otherwise every write fails silently
    # with "database disk image is malformed" while reads still succeed,
    # which is very confusing to debug. Better to fail fast and loud.
    try:
        result = state.write_conn.execute("PRAGMA integrity_check").fetchone()
        if result and result[0] != "ok":
            print(f"FATAL: {CATALOG_DB} is corrupt ({result[0]})")
            print(f"Fix: rm -f {CATALOG_DB} {CATALOG_DB}-wal {CATALOG_DB}-shm, then restart")
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"integrity check skipped: {e}")

    state.background_task = asyncio.create_task(catalog_worker.maintenance_loop())
    state.probe_task = asyncio.create_task(providers.probe_loop())
    try:
        yield
    finally:
        for t in (state.background_task, state.probe_task):
            if t is not None:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        if state.client is not None:
            await state.client.aclose()
            state.client = None
        if state.write_conn is not None:
            state.write_conn.close()
            state.write_conn = None


app = FastAPI(
    title="MovieBox API Pro",
    description="Full Pure REST API for moviebox.ph — Zero Scraping",
    version=API_VERSION,
    contact={
        "name": "Faisal",
        "url": "https://github.com/faisaljs",
    },
    license_info={
        "name": "MIT",
        "url": "https://github.com/faisaljs/Moviebox-API/blob/main/LICENSE",
    },
    lifespan=lifespan,
)

_rate_windows: dict[tuple[str, str], tuple[int, int]] = {}
_rate_checks = 0
_EXPENSIVE_PREFIXES = (
    "/catalog/refresh", "/catalog/add", "/api/tabs", "/api/debug/",
    "/providers/probe", "/search", "/detail/", "/api/stream/",
)


def _authorized(header: str | None) -> bool:
    if not header:
        return False
    scheme, separator, encoded = header.partition(" ")
    if not separator or scheme.lower() != "basic":
        return False
    try:
        raw = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, separator, password = raw.partition(":")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    if not separator:
        return False
    return hmac.compare_digest(username, AUTH_USER) & hmac.compare_digest(password, AUTH_PASSWORD)


@app.middleware("http")
async def production_guards(request: Request, call_next):
    global _rate_checks
    is_liveness = request.method == "GET" and request.url.path == "/health"
    if AUTH_ENABLED and not is_liveness and not _authorized(request.headers.get("authorization")):
        response = JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": 'Basic realm="MovieBox", charset="UTF-8"'},
        )
    else:
        client_host = request.client.host if request.client else "unknown"
        expensive = request.url.path.startswith(_EXPENSIVE_PREFIXES)
        limit = EXPENSIVE_RATE_LIMIT_PER_MINUTE if expensive else RATE_LIMIT_PER_MINUTE
        window = int(time.time() // 60)
        key = (client_host, "expensive" if expensive else "general")
        old_window, count = _rate_windows.get(key, (window, 0))
        if old_window != window:
            count = 0
        if count >= limit:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Request rate limit exceeded"},
                headers={"Retry-After": str(60 - int(time.time() % 60))},
            )
        else:
            _rate_windows[key] = (window, count + 1)
            _rate_checks += 1
            if _rate_checks % 256 == 0:
                _rate_windows_copy = dict(_rate_windows)
                _rate_windows.clear()
                _rate_windows.update({k: v for k, v in _rate_windows_copy.items() if v[0] >= window})
            response = await call_next(request)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith(("/user/", "/recommendations")):
        response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data: https:; media-src 'self' blob: https:; "
        "font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline'",
    )
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.middleware("http")
async def reject_cross_origin_mutations(request: Request, call_next):
    # The app has no login cookie to provide CSRF protection. Reject browser
    # form/fetch mutations from untrusted origins while allowing native clients
    # that do not send Origin and explicitly configured web clients.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
            same_origin = f"{scheme}://{request.headers.get('host', request.url.netloc)}"
            if origin.rstrip("/") not in {same_origin.rstrip("/"), *CORS_ORIGINS}:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-origin mutations are not allowed"},
                )
    return await call_next(request)


if CORS_ORIGINS:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=AUTH_ENABLED,
    )

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json")
async def manifest():
    path = os.path.join(STATIC_DIR, "manifest.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/manifest+json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/sw.js")
async def service_worker():
    path = os.path.join(STATIC_DIR, "sw.js")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Response(
                content=f.read(),
                media_type="application/javascript",
                headers={"Service-Worker-Allowed": "/"},
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="sw.js not found")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/app", response_class=HTMLResponse)
async def frontend_app():
    path = os.path.join(STATIC_DIR, "app.html")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>app.html not found in static/</h1>", status_code=404)


if __name__ == "__main__":
    import uvicorn
    reload_flag = os.environ.get("RELOAD", "0") == "1"
    uvicorn.run("main:app", host=BIND_HOST, port=PORT, reload=reload_flag)
