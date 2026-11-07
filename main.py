"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT

Pure REST API for moviebox.ph. Stateless proxy — no UI, no DB, no persistence.
"""

import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

import state
import providers
from config import (
    API_VERSION, PORT, BIND_HOST, CORS_ORIGINS, REQUEST_TIMEOUT,
)
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
    state.probe_task = asyncio.create_task(providers.probe_loop())
    try:
        yield
    finally:
        if state.probe_task is not None:
            state.probe_task.cancel()
            try:
                await state.probe_task
            except asyncio.CancelledError:
                pass
        if state.client is not None:
            await state.client.aclose()
            state.client = None


app = FastAPI(
    title="MovieBox API Pro",
    description="Pure REST API for moviebox.ph. Stateless proxy — no UI, no DB, no persistence.",
    version=API_VERSION,
    contact={"name": "Faisal", "url": "https://github.com/faisaljs"},
    license_info={
        "name": "MIT",
        "url": "https://github.com/faisaljs/Moviebox-API/blob/main/LICENSE",
    },
    lifespan=lifespan,
)


@app.middleware("http")
async def reject_cross_origin_mutations(request: Request, call_next):
    # No auth cookie exists, so CSRF isn't strictly possible — but reject
    # browser-originated mutations from untrusted origins anyway.
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

DASHBOARD_PATH = Path(__file__).parent / "api_dashboard.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    if not DASHBOARD_PATH.is_file():
        return HTMLResponse(
            "<h1>api_dashboard.html not found in app directory</h1>",
            status_code=404,
        )
    return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))

if __name__ == "__main__":
    import uvicorn
    reload_flag = os.environ.get("RELOAD", "0") == "1"
    uvicorn.run("main:app", host=BIND_HOST, port=PORT, reload=reload_flag)