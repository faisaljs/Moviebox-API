"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import asyncio
from fastapi import APIRouter, HTTPException
import state
import storage
import upstream
import catalog_worker
from config import (
    DEFAULT_HOST, KNOWN_HOSTS,
    CATALOG_DB, CATALOG_REFRESH_INTERVAL, CATALOG_KEYWORDS,
    TAB_MOVIES, TAB_TV, TAB_ANIMATION, CATALOG_SECTIONS,
)
from helpers import normalize_subject_item

router = APIRouter()


def _row_to_item(r) -> dict:
    return {
        "name": r["title"],
        "poster_url": r["poster_url"],
        "slug": r["slug"],
        "subject_id": r["subject_id"],
        "rating": r["rating"],
        "year": r["year"],
        "badge": r["badge"],
        "subject_type": r["subject_type"],
        "genre": r["genre"],
        "source_host": r["source_host"],
        "types": [
            t for t, f in (("movie", r["is_movie"]), ("tv", r["is_tv"]), ("anime", r["is_anime"])) if f
        ],
    }


@router.get("/catalog")
async def catalog(
    type: str = "all",
    sort: str = "recent",
    page: int = 1,
    per_page: int = 24,
    q: str | None = None,
    host: str | None = None,
):
    where = []
    params: list = []
    if type == "movie":
        where.append("is_movie = 1")
    elif type == "tv":
        where.append("is_tv = 1")
    elif type == "anime":
        where.append("is_anime = 1")
    elif type not in ("all", ""):
        raise HTTPException(400, detail=f"Unknown type: {type} (all|movie|tv|anime)")

    if q:
        fts_ids = storage.fts_search(q)
        if fts_ids is None:
            where.append("title LIKE ?")
            params.append(f"%{q}%")
        elif fts_ids:
            where.append(f"subject_id IN ({','.join('?' * len(fts_ids))})")
            params.extend(fts_ids)
        else:
            where.append("1 = 0")
    if host:
        where.append("source_host = ?")
        params.append(host)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    if sort == "title":
        order = "title COLLATE NOCASE ASC"
    elif sort == "rating":
        order = "CAST(rating AS REAL) DESC NULLS LAST"
    elif sort == "recent":
        order = "last_seen DESC"
    else:
        raise HTTPException(400, detail=f"Unknown sort: {sort} (recent|title|rating)")

    per_page = max(1, min(per_page, 100))
    offset = (max(1, page) - 1) * per_page
    total = storage.read_scalar(f"SELECT COUNT(*) FROM subjects {where_sql}", tuple(params)) or 0
    rows = storage.read(
        f"""
        SELECT subject_id, title, poster_url, slug, rating, year, badge,
               is_movie, is_tv, is_anime, subject_type, genre, source_host
        FROM subjects {where_sql}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        tuple(params + [per_page, offset]),
    )

    # When local FTS finds nothing for a text query, fall back to upstream
    # search (handles abbreviations + typo tolerance that FTS5 can't).
    if q and total == 0 and type in ("all", "") and not host:
        try:
            up_data = await upstream.bff_request(
                "/subject/search", method="POST",
                payload={"keyword": q, "page": page, "perPage": per_page},
            )
            inner = up_data.get("data", {}) or {}
            raw = inner.get("items") or inner.get("list") or []
            up_items = [
                {
                    "name": sub.get("title"),
                    "poster_url": (sub.get("cover") or {}).get("url"),
                    "slug": sub.get("detailPath"),
                    "subject_id": sub.get("subjectId"),
                    "rating": sub.get("imdbRatingValue"),
                    "year": (sub.get("releaseDate") or "")[:4] or None,
                    "badge": sub.get("corner"),
                    "subject_type": None,
                    "genre": None,
                    "source_host": "upstream",
                    "types": [],
                }
                for sub in raw
            ]
            pager = inner.get("pager", {}) or {}
            up_total = pager.get("totalCount") or inner.get("total") or len(up_items)
            return {
                "type": type, "sort": sort, "query": q, "host": "upstream",
                "page": page, "per_page": per_page,
                "total": up_total,
                "total_pages": (up_total + per_page - 1) // per_page if per_page else 0,
                "items": up_items,
                "source": "upstream_fallback",
            }
        except Exception:
            pass

    return {
        "type": type, "sort": sort, "query": q, "host": host,
        "page": page, "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if per_page else 0,
        "items": [_row_to_item(r) for r in rows],
        "source": "local",
    }


@router.get("/catalog/stats")
async def catalog_stats():
    total = storage.read_scalar("SELECT COUNT(*) FROM subjects") or 0
    movies = storage.read_scalar("SELECT COUNT(*) FROM subjects WHERE is_movie = 1") or 0
    tv = storage.read_scalar("SELECT COUNT(*) FROM subjects WHERE is_tv = 1") or 0
    anime = storage.read_scalar("SELECT COUNT(*) FROM subjects WHERE is_anime = 1") or 0
    untyped = storage.read_scalar(
        "SELECT COUNT(*) FROM subjects WHERE is_movie = 0 AND is_tv = 0 AND is_anime = 0"
    ) or 0
    untyped_pending = storage.read_scalar(
        "SELECT COUNT(*) FROM subjects WHERE subject_type IS NULL AND slug IS NOT NULL"
    ) or 0
    subject_types = {
        str(r[0]): r[1] for r in storage.read(
            "SELECT subject_type, COUNT(*) FROM subjects WHERE subject_type IS NOT NULL GROUP BY subject_type"
        )
    }
    by_host = {
        r[0]: r[1] for r in storage.read(
            "SELECT source_host, COUNT(*) FROM subjects GROUP BY source_host"
        )
    }
    kw_rows = storage.read(
        "SELECT keyword, pages_walked, items_seen, hit_cap, total_per_upstream FROM keyword_stats ORDER BY keyword"
    )
    keyword_stats = {
        r["keyword"]: {
            "pages": r["pages_walked"],
            "items": r["items_seen"],
            "hit_cap": bool(r["hit_cap"]),
            "upstream_total": r["total_per_upstream"],
        }
        for r in kw_rows
    }
    return {
        "total": total,
        "movies": movies,
        "tv": tv,
        "anime": anime,
        "untyped": untyped,
        "untyped_pending_enrichment": untyped_pending,
        "subject_types": subject_types,
        "by_host": by_host,
        "bookmarks_count": storage.read_scalar("SELECT COUNT(*) FROM user_bookmarks") or 0,
        "history_count": storage.read_scalar("SELECT COUNT(*) FROM user_history") or 0,
        "db_path": CATALOG_DB,
        "refresh_interval_seconds": CATALOG_REFRESH_INTERVAL,
        "keywords_total": len(CATALOG_KEYWORDS),
        "known_hosts": KNOWN_HOSTS,
        "walk_state": state.walk_state,
        "keyword_stats": keyword_stats,
    }


@router.post("/catalog/refresh")
async def catalog_refresh(mode: str = "full", force: bool = False):
    if mode == "enrich":
        if state.walk_state.get("enriching"):
            return {"status": "enrich_already_running", "walk_state": state.walk_state}
        asyncio.create_task(catalog_worker.run_enrichment())
        return {"status": "enrich_queued"}
    if state.walk_state.get("running"):
        return {"status": "walk_already_running", "walk_state": state.walk_state}

    async def _full():
        await catalog_worker.run_full_walk(force=force)
        await catalog_worker.run_enrichment()

    asyncio.create_task(_full())
    return {"status": "full_queued", "force": force}


@router.post("/catalog/add")
async def catalog_add(slug: str, host: str | None = None):
    h = host or DEFAULT_HOST
    data = await upstream.bff_request(f"/detail?detailPath={slug}", preferred_host=h)
    sub = (data.get("data") or {}).get("subject") or {}
    if not sub.get("subjectId"):
        raise HTTPException(502, detail="Detail response has no subject")
    storage.upsert_subject(sub, source_host=h)
    state.commit()
    row = storage.read(
        "SELECT subject_id, slug, source_host FROM subjects WHERE subject_id=?",
        (str(sub["subjectId"]),),
    )
    if row:
        await catalog_worker.enrich_subject(row[0])
        state.commit()
    return {
        "status": "added",
        "subject_id": str(sub["subjectId"]),
        "title": sub.get("title"),
        "subject_type": sub.get("subjectType"),
        "genre": sub.get("genre"),
        "host": h,
    }


# ─── HOME FALLBACK CATALOGS ──────────────────────────────────────────────────

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
    ops = await catalog_worker.get_home_operating_list(host)
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
        f"Try /sections to list available sections, /browse/{{section}}, or /catalog."
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