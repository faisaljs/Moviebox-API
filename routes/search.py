import asyncio
from fastapi import APIRouter, Query
import upstream
from config import DEFAULT_HOST

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=1), page: int = 1, host: str = DEFAULT_HOST):
    data = await upstream.bff_request(
        "/subject/search", method="POST",
        payload={"keyword": q, "page": page, "perPage": 20},
        preferred_host=host,
    )
    inner = data.get("data", {}) or {}
    raw = inner.get("items") or inner.get("list") or []
    items = [
        {
            "name": sub.get("title"),
            "poster_url": (sub.get("cover") or {}).get("url"),
            "slug": sub.get("detailPath"),
            "subject_id": sub.get("subjectId"),
        }
        for sub in raw
    ]
    pager = inner.get("pager", {}) or {}
    total = pager.get("totalCount") or inner.get("total") or len(items)
    return {"query": q, "host": host, "page": page, "total": total, "items": items}


async def _enrich_suggestion(title: str, host: str) -> dict:
    try:
        data = await upstream.bff_request(
            "/subject/search", method="POST",
            payload={"keyword": title, "page": 1, "perPage": 1},
            preferred_host=host,
        )
        inner = data.get("data", {}) or {}
        raw = inner.get("items") or inner.get("list") or []
        if raw:
            sub = raw[0]
            return {
                "title": sub.get("title") or title,
                "slug": sub.get("detailPath"),
                "subject_id": sub.get("subjectId"),
            }
    except Exception:
        pass
    return {"title": title, "slug": None, "subject_id": None}


@router.get("/search/suggest")
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    enrich: bool = False,
    host: str = DEFAULT_HOST,
):
    data = await upstream.bff_request(
        "/subject/search-suggest", method="POST",
        payload={"keyword": q, "perPage": 10}, preferred_host=host,
    )
    inner = data.get("data", {}) or {}
    raw = inner.get("items") or inner.get("list") or []
    titles: list[str] = []
    for item in raw:
        title = (
            (item.get("subject") or {}).get("title")
            or item.get("word")
            or item.get("title")
            or item.get("keyword")
        )
        if title and title not in titles:
            titles.append(title)

    if enrich:
        suggestions = await asyncio.gather(*(_enrich_suggestion(t, host) for t in titles))
    else:
        suggestions = [{"title": t} for t in titles]

    return {"query": q, "host": host, "count": len(suggestions), "suggestions": suggestions}


@router.get("/detail/{slug}")
async def get_movie_detail(slug: str, host: str = DEFAULT_HOST):
    return await upstream.bff_request(f"/detail?detailPath={slug}", preferred_host=host)