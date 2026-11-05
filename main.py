"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import os
import sqlite3
import asyncio
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
    state.write_conn = sqlite3.connect(CATALOG_DB, check_same_thread=False)
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
