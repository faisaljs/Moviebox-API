from fastapi import APIRouter
from . import providers, home, catalog, search, stream, diagnostics

router = APIRouter()
for _r in (
    providers.router,
    home.router,
    catalog.router,
    search.router,
    stream.router,
    diagnostics.router,
):
    router.include_router(_r)