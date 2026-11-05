"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import time
import asyncio
from config import (
    CATALOG_KEYWORDS, CATALOG_MAX_PAGES_PER_KEYWORD, CATALOG_REFRESH_INTERVAL,
    DEFAULT_HOST, KNOWN_HOSTS, ENRICH_RATE_LIMIT, ENRICH_BATCH_SIZE,
)
import state
import storage
import upstream
from fastapi import HTTPException




async def get_home_operating_list(host: str | None = DEFAULT_HOST) -> list:
    h = host or DEFAULT_HOST
    now = time.time()
    cached = state.home_cache.get(h)
    if cached and now < cached[1]:
        return cached[0]
    data = await upstream.bff_request("/home", preferred_host=host)
    ops = data.get("data", {}).get("operatingList", []) or []
    state.home_cache[h] = (ops, now + 300)
    return ops


async def ingest_home_sections(host: str = DEFAULT_HOST) -> int:
    try:
        ops = await get_home_operating_list(host)
    except Exception:
        return 0
    count = 0
    for op in ops:
        op_type = op.get("type")
        section_title = op.get("title", "")
        if op_type not in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            continue
        for raw in op.get("subjects", []) or []:
            if storage.upsert_subject(raw, section=section_title, source_host=host):
                count += 1
    if state.write_conn is not None:
        state.write_conn.commit()
    return count


async def walk_keyword(host: str, kw: str) -> int:
    seen = 0
    pages = 0
    hit_cap = 0
    total_upstream = None
    for page in range(1, CATALOG_MAX_PAGES_PER_KEYWORD + 1):
        try:
            data = await upstream.bff_request(
                "/subject/search",
                method="POST",
                payload={"keyword": kw, "page": page, "perPage": 20},
                preferred_host=host,
            )
        except HTTPException:
            break
        inner = data.get("data", {}) or {}
        items = inner.get("items") or inner.get("list") or []
        if not items:
            break
        if state.write_conn is None:
            break
        for sub in items:
            if storage.upsert_subject(sub, source_host=host):
                seen += 1
        state.write_conn.commit()
        pages = page
        pager = inner.get("pager") or {}
        if total_upstream is None:
            total_upstream = pager.get("totalCount")
        if not pager.get("hasMore"):
            break
        if page == CATALOG_MAX_PAGES_PER_KEYWORD:
            hit_cap = 1
    try:
        state.write_conn.execute("""
            INSERT INTO keyword_stats (keyword, pages_walked, items_seen, hit_cap, total_per_upstream, last_walked)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(keyword) DO UPDATE SET
                pages_walked = excluded.pages_walked,
                items_seen = excluded.items_seen,
                hit_cap = excluded.hit_cap,
                total_per_upstream = excluded.total_per_upstream,
                last_walked = excluded.last_walked
        """, (kw, pages, seen, hit_cap, total_upstream, time.time()))
        state.write_conn.commit()
    except Exception as e:
        print(f"keyword_stats {kw} failed: {e}")
    return seen


async def run_full_walk(force: bool = False):
    if state.walk_state.get("running"):
        return
    state.walk_state.update({
        "running": True,
        "started_at": time.time(),
        "keywords_done": 0,
        "keywords_total": len(CATALOG_KEYWORDS),
        "items_seen": 0,
        "current_host": None,
        "hosts_processed": [],
        "unique_hosts": [],
        "force": force,
    })
    try:
        primary_ops = await get_home_operating_list(KNOWN_HOSTS[0])
        primary_hash = storage.hash_operating_list(primary_ops)
        unique_hosts = [KNOWN_HOSTS[0]]
        state.walk_state["hosts_processed"].append({
            "host": KNOWN_HOSTS[0], "status": "primary", "hash": primary_hash,
        })

        if force:
            for host in KNOWN_HOSTS[1:]:
                unique_hosts.append(host)
                state.walk_state["hosts_processed"].append({"host": host, "status": "forced"})
        else:
            for host in KNOWN_HOSTS[1:]:
                try:
                    ops = await get_home_operating_list(host)
                    h = storage.hash_operating_list(ops)
                    if h == primary_hash:
                        state.walk_state["hosts_processed"].append({"host": host, "status": "duplicate", "hash": h})
                    else:
                        unique_hosts.append(host)
                        state.walk_state["hosts_processed"].append({"host": host, "status": "unique", "hash": h})
                except Exception as e:
                    state.walk_state["hosts_processed"].append({"host": host, "status": "dead", "error": str(e)[:80]})

        state.walk_state["unique_hosts"] = unique_hosts
        state.walk_state["keywords_total"] = len(CATALOG_KEYWORDS) * len(unique_hosts)

        for host in unique_hosts:
            state.walk_state["current_host"] = host
            await ingest_home_sections(host)
            for kw in CATALOG_KEYWORDS:
                try:
                    count = await walk_keyword(host, kw)
                    state.walk_state["keywords_done"] += 1
                    state.walk_state["items_seen"] += count
                except Exception as e:
                    print(f"walk {host} {kw!r} failed: {e}")
                    state.walk_state["keywords_done"] += 1

        state.walk_state["finished_at"] = time.time()
        state.walk_state["duration_seconds"] = round(state.walk_state["finished_at"] - state.walk_state["started_at"], 1)
        state.walk_state["total_indexed"] = storage.read_scalar("SELECT COUNT(*) FROM subjects") or 0
    finally:
        state.walk_state["running"] = False
        state.walk_state["current_host"] = None


def classify_from_detail(subject_type, genre: str | None) -> tuple[int, int, int] | None:
    if subject_type == 1:
        return (1, 0, 0)
    if subject_type == 2:
        if genre and "anime" in genre.lower():
            return (0, 0, 1)
        return (0, 1, 0)
    if subject_type == 6:
        return (0, 0, 0)
    return None


async def enrich_subject(row) -> bool:
    sid = row["subject_id"]
    slug = row["slug"]
    host = row["source_host"] or DEFAULT_HOST
    if not slug:
        return False
    try:
        data = await upstream.bff_request(f"/detail?detailPath={slug}", preferred_host=host)
    except HTTPException:
        return False
    sub = (data.get("data") or {}).get("subject") or {}
    stype = sub.get("subjectType")
    genre = sub.get("genre") or ""
    classification = classify_from_detail(stype, genre)
    if classification is None:
        try:
            state.write_conn.execute(
                "UPDATE subjects SET subject_type=0, genre=? WHERE subject_id=?",
                (genre, sid),
            )
            return True
        except Exception:
            return False
    is_movie, is_tv, is_anime = classification
    try:
        state.write_conn.execute(
            "UPDATE subjects SET subject_type=?, genre=?, is_movie=?, is_tv=?, is_anime=? WHERE subject_id=?",
            (stype, genre, is_movie, is_tv, is_anime, sid),
        )
        return True
    except Exception as e:
        print(f"enrich {sid} failed: {e}")
        return False


async def run_enrichment():
    if state.walk_state.get("enriching"):
        return
    state.walk_state["enriching"] = True
    enriched = 0
    failed = 0
    try:
        # Snapshot pending rows so failures are not selected repeatedly in
        # this run and cannot keep the worker in an endless retry loop.
        rows = storage.read("""
            SELECT subject_id, slug, source_host FROM subjects
            WHERE subject_type IS NULL
              AND slug IS NOT NULL
            ORDER BY first_seen
        """)
        for start in range(0, len(rows), ENRICH_BATCH_SIZE):
            for row in rows[start:start + ENRICH_BATCH_SIZE]:
                ok = await enrich_subject(row)
                if ok:
                    enriched += 1
                else:
                    failed += 1
                if state.write_conn is not None:
                    state.write_conn.commit()
                await asyncio.sleep(ENRICH_RATE_LIMIT)
            state.walk_state["enrich_progress"] = {
                "enriched": enriched,
                "failed": failed,
                "remaining": storage.read_scalar(
                    "SELECT COUNT(*) FROM subjects WHERE subject_type IS NULL AND slug IS NOT NULL"
                ) or 0,
            }
        state.walk_state["enrich_progress"] = {
            "enriched": enriched,
            "failed": failed,
            "remaining": storage.read_scalar(
                "SELECT COUNT(*) FROM subjects WHERE subject_type IS NULL AND slug IS NOT NULL"
            ) or 0,
            "finished_at": time.time(),
        }
    finally:
        state.walk_state["enriching"] = False


async def maintenance_loop():
    await asyncio.sleep(2)
    try:
        if (storage.read_scalar("SELECT COUNT(*) FROM subjects") or 0) == 0:
            await run_full_walk()
        await run_enrichment()
    except Exception as e:
        print(f"initial catalog setup failed: {e}")
    while True:
        try:
            await asyncio.sleep(CATALOG_REFRESH_INTERVAL)
            await run_full_walk()
            await run_enrichment()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"catalog refresh failed: {e}")
