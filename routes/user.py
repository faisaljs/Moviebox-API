"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

from fastapi import APIRouter
import state
import storage
from schemas import BookmarkIn, HistoryIn

router = APIRouter()


@router.get("/user/bookmarks")
async def get_user_bookmarks():
    return {"bookmarks": storage.get_bookmarks()}


@router.post("/user/bookmarks")
async def add_user_bookmark(body: BookmarkIn):
    storage.upsert_bookmark(body.model_dump(exclude_none=True))
    state.commit()
    return {"status": "saved", "slug": body.slug}


@router.delete("/user/bookmarks/{slug}")
async def delete_user_bookmark(slug: str):
    deleted = storage.delete_bookmark(slug)
    state.commit()
    return {"status": "deleted" if deleted else "not_found", "slug": slug}


@router.delete("/user/bookmarks")
async def clear_user_bookmarks():
    n = storage.clear_bookmarks()
    state.commit()
    return {"deleted": n}


@router.get("/user/history")
async def get_user_history():
    return {"history": storage.get_history()}


@router.post("/user/history")
async def add_user_history(body: HistoryIn):
    storage.upsert_history(body.model_dump(exclude_none=True))
    state.commit()
    return {"status": "saved"}


@router.delete("/user/history/{slug}")
async def delete_user_history(slug: str, se: int | None = None, ep: int | None = None):
    n = storage.delete_history(slug, se, ep)
    state.commit()
    return {"deleted": n}


@router.delete("/user/history")
async def clear_user_history():
    n = storage.clear_history()
    state.commit()
    return {"deleted": n}


@router.get("/recommendations")
async def get_recommendations(limit: int = 20):
    capped = max(1, min(limit, 50))
    items = storage.recommend(limit=capped)
    return {"count": len(items), "items": items}


@router.get("/recommendations/because/{slug}")
async def get_because(slug: str, limit: int = 12):
    capped = max(1, min(limit, 30))
    return storage.recommend_because(slug, limit=capped)