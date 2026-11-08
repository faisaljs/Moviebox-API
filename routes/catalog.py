from fastapi import APIRouter
import upstream
from config import (
    DEFAULT_HOST, TAB_MOVIES, TAB_TV, TAB_ANIMATION, CATALOG_SECTIONS,
)
from helpers import normalize_subject_item

router = APIRouter()


async def _get_category_data(tab_id: int, page: int = 1, per_page: int = 24, sort: str = "RECOMMEND") -> dict:
    data = await upstream.bff_request("/subject/filter", method="POST", payload={
        "tabId": tab_id,
        "filter": {
            "sort": sort, "genre": "ALL", "country": "ALL",
            "year": "ALL", "language": "ALL",
        },
        "page": page,
        "perPage": per_page,
    })
    inner = data.get("data", {}) or {}
    raw_items = inner.get("items") or inner.get("subjects") or []
    items = [
        {
            "name": sub.get("title"),
            "poster_url": (sub.get("cover") or {}).get("url"),
            "slug": sub.get("detailPath"),
            "subject_id": sub.get("subjectId"),
            "badge": sub.get("corner"),
            "rating": sub.get("imdbRatingValue"),
            "year": (sub.get("releaseDate") or "")[:4] or None,
        }
        for sub in raw_items
    ]
    pager = inner.get("pager", {}) or {}
    total = pager.get("totalCount") or inner.get("total") or len(items)
    sentinel = bool(total and total >= 1000000)
    return {
        "tab_id": tab_id, "page": page, "per_page": per_page,
        "total": None if sentinel else total,
        "total_sentinel": sentinel,
        "source": "filter",
        "items": items,
    }


async def _catalog_from_home(
    keywords: list[str], page: int, host: str | None = DEFAULT_HOST, per_page: int = 24,
) -> dict | None:
    ops = await upstream.get_home_operating_list(host)
    matched_items: list[dict] = []
    seen_ids: set[str] = set()
    matched_sections: set[str] = set()
    for op in ops:
        op_type = op.get("type")
        title = op.get("title", "")
        if not any(kw.lower() in title.lower() for kw in keywords):
            continue
        if op_type not in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            continue
        matched_sections.add(title)
        for raw in op.get("subjects", []) or []:
            item = normalize_subject_item(raw)
            sid = str(item.get("subject_id")) if item and item.get("subject_id") else None
            if item and sid and sid not in seen_ids:
                seen_ids.add(sid)
                matched_items.append(item)
    if not matched_items:
        return None
    start = (page - 1) * per_page
    return {
        "page": page, "per_page": per_page,
        "total": len(matched_items), "total_sentinel": False,
        "source": "home_fallback", "host": host or DEFAULT_HOST,
        "sections": sorted(matched_sections),
        "items": matched_items[start:start + per_page],
    }


async def _catalog(kind: str, tab_id: int, page: int, sort: str, source: str, host: str) -> dict:
    if source in ("auto", "filter"):
        result = await _get_category_data(tab_id, page=page, sort=sort)
        if not result["total_sentinel"] or source == "filter":
            return result
    fallback = await _catalog_from_home(CATALOG_SECTIONS[kind], page=page, host=host)
    if fallback:
        return fallback
    result = await _get_category_data(tab_id, page=page, sort=sort)
    result["source"] = "filter_sentinel_no_fallback"
    result["note"] = (
        f"No home sections matched for '{kind}'. "
        f"Try /sections to list available sections, /browse/{{section}}."
    )
    return result


@router.get("/movies")
async def get_movies(page: int = 1, sort: str = "RECOMMEND", tab: int | None = None,
                     source: str = "auto", host: str = DEFAULT_HOST):
    return await _catalog("movies", tab if tab is not None else TAB_MOVIES, page, sort, source, host)


@router.get("/tv-series")
async def get_tv_series(page: int = 1, sort: str = "RECOMMEND", tab: int | None = None,
                        source: str = "auto", host: str = DEFAULT_HOST):
    return await _catalog("tv-series", tab if tab is not None else TAB_TV, page, sort, source, host)


@router.get("/animation")
async def get_animation(page: int = 1, sort: str = "RECOMMEND", tab: int | None = None,
                        source: str = "auto", host: str = DEFAULT_HOST):
    return await _catalog("animation", tab if tab is not None else TAB_ANIMATION, page, sort, source, host)