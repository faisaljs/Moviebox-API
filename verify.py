"""
Live verification for MovieBox API Pro v2.9.1.

Author: Faisal (https://github.com/faisaljs)
Repo:   https://github.com/faisaljs/Moviebox-API
License: MIT

Run against a live server: python verify.py [base_url]
Default: http://localhost:8000
"""

import sys
import httpx
import time

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TIMEOUT = 90


def hr(label):
    print(f"\n{'─' * 60}\n{label}\n{'─' * 60}")


def ok(cond, msg):
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {msg}")
    return cond


def sample_items(items, label):
    print(f"    {label}: {len(items)} items")
    if items:
        it = items[0]
        print(f"    sample: name={str(it.get('name'))[:50]!r}")
        print(f"            slug={it.get('slug')}")
        print(f"            sid={it.get('subject_id')}")
        print(f"            poster={'YES' if it.get('poster_url') else 'NULL'}")
    return items


results = {"pass": 0, "fail": 0}


def record(passed):
    results["pass" if passed else "fail"] += 1


# ── 1. dashboard ────────────────────────────────────────────────────────────
hr("GET /  (dashboard)")
try:
    r = httpx.get(f"{BASE}/", timeout=TIMEOUT)
    is_html = r.status_code == 200 and "<html" in r.text.lower()
    record(ok(is_html, f"status {r.status_code}, html={'YES' if is_html else 'NO'}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 2. home ────────────────────────────────────────────────────────────────
hr("GET /home")
home_slug = home_sid = None
try:
    r = httpx.get(f"{BASE}/home", timeout=TIMEOUT)
    data = r.json()
    secs = data.get("sections", [])
    record(ok(r.status_code == 200 and len(secs) > 0, f"status {r.status_code}, {len(secs)} sections"))
    for s in secs[:4]:
        items = s.get("items", [])
        print(f"    [{s['section']}] {s['count']} items")
        if items and not home_slug:
            first = items[0]
            home_slug = first.get("slug")
            home_sid = first.get("subject_id")
            print(f"    picked: slug={home_slug} sid={home_sid}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 3. catalog stats ───────────────────────────────────────────────────────
hr("GET /catalog/stats")
try:
    r = httpx.get(f"{BASE}/catalog/stats", timeout=TIMEOUT)
    data = r.json()
    total = data.get("total", 0)
    walk = data.get("walk_state", {})
    record(ok(r.status_code == 200 and "walk_state" in data,
              f"status {r.status_code}, total={total}, "
              f"walk_running={walk.get('running')}, "
              f"enriching={walk.get('enriching')}"))
    print(f"    types: movies={data.get('movies')} tv={data.get('tv')} anime={data.get('anime')} "
          f"untyped={data.get('untyped')} pending_enrich={data.get('untyped_pending_enrichment')}")
    st = data.get("subject_types", {})
    if st:
        print(f"    subject_type breakdown: {st}")
    ks = data.get("keyword_stats", {})
    if ks:
        cap_kws = [k for k, v in ks.items() if v.get("hit_cap")]
        print(f"    keywords walked: {len(ks)}/36, hit_cap: {cap_kws}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 4. catalog (indexed) ───────────────────────────────────────────────────
hr("GET /catalog")
try:
    r = httpx.get(f"{BASE}/catalog", params={"per_page": 12}, timeout=TIMEOUT)
    data = r.json()
    items = data.get("items", [])
    total = data.get("total", 0)
    schema_ok = "total" in data and "items" in data and "page" in data
    record(ok(r.status_code == 200 and schema_ok, f"status {r.status_code}, total={total}, items={len(items)}"))
    if items:
        sample_items(items, "catalog")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 5. catalog sorts ───────────────────────────────────────────────────────
hr("GET /catalog?sort=title  and  ?sort=rating")
for sort in ("title", "rating"):
    try:
        r = httpx.get(f"{BASE}/catalog", params={"sort": sort, "per_page": 3}, timeout=TIMEOUT)
        data = r.json()
        record(ok(r.status_code == 200, f"sort={sort}, status {r.status_code}, total={data.get('total')}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))

# ── 6. catalog type filters ────────────────────────────────────────────────
hr("GET /catalog?type=movie  /  ?type=tv  /  ?type=anime")
for t in ("movie", "tv", "anime"):
    try:
        r = httpx.get(f"{BASE}/catalog", params={"type": t, "per_page": 3}, timeout=TIMEOUT)
        data = r.json()
        record(ok(r.status_code == 200, f"type={t}, status {r.status_code}, total={data.get('total')}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))

# ── 7. catalog text search ─────────────────────────────────────────────────
hr("GET /catalog?q=the")
try:
    r = httpx.get(f"{BASE}/catalog", params={"q": "the", "per_page": 3}, timeout=TIMEOUT)
    data = r.json()
    items = data.get("items", [])
    record(ok(r.status_code == 200, f"status {r.status_code}, matches={data.get('total')}"))
    sample_items(items, "q=the")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 8. catalog refresh ─────────────────────────────────────────────────────
hr("POST /catalog/refresh")
try:
    r = httpx.post(f"{BASE}/catalog/refresh", timeout=TIMEOUT)
    data = r.json()
    record(ok(r.status_code == 200 and "status" in data,
              f"status {r.status_code}, response={data.get('status')}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 9. home fallback catalogs ──────────────────────────────────────────────
for path in ("/movies", "/tv-series", "/animation"):
    hr(f"GET {path}")
    try:
        r = httpx.get(f"{BASE}{path}", timeout=TIMEOUT)
        data = r.json()
        items = data.get("items", [])
        record(ok(r.status_code == 200 and len(items) > 0,
                  f"status {r.status_code}, source={data.get('source')}, total={data.get('total')}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))

# ── 10. search ─────────────────────────────────────────────────────────────
hr("GET /search?q=matrix")
try:
    r = httpx.get(f"{BASE}/search", params={"q": "matrix"}, timeout=TIMEOUT)
    data = r.json()
    record(ok(r.status_code == 200, f"status {r.status_code}, total={data.get('total')}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 11. detail ─────────────────────────────────────────────────────────────
hr("GET /detail/{slug}")
if home_slug:
    try:
        r = httpx.get(f"{BASE}/detail/{home_slug}", timeout=TIMEOUT)
        data = r.json()
        inner = data.get("data", {}) or {}
        record(ok(r.status_code == 200 and bool(inner), f"status {r.status_code}, keys={list(inner.keys())[:6]}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no slug from /home"))

# ── 12. stream ─────────────────────────────────────────────────────────────
hr("GET /api/stream/{sid}")
if home_sid and home_slug:
    try:
        r = httpx.get(
            f"{BASE}/api/stream/{home_sid}",
            params={"detail_path": home_slug},
            timeout=TIMEOUT,
        )
        data = r.json()
        record(ok(r.status_code == 200, f"status {r.status_code}, has_resource={data.get('has_resource')}, sources={len(data.get('sources', []))}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no sid"))

# ── 13. captions ───────────────────────────────────────────────────────────
hr("GET /api/stream/{sid}/captions")
captions_lang = None
if home_sid and home_slug:
    try:
        r = httpx.get(
            f"{BASE}/api/stream/{home_sid}/captions",
            params={"detail_path": home_slug},
            timeout=TIMEOUT,
        )
        data = r.json()
        caps = data.get("captions", [])
        record(ok(r.status_code == 200, f"status {r.status_code}, count={data.get('count')}"))
        if caps:
            captions_lang = caps[0].get("lan")
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no sid"))

# ── 14. proxy ──────────────────────────────────────────────────────────────
hr("GET /api/stream/{sid}/proxy  (Range)")
if home_sid and home_slug:
    try:
        with httpx.stream(
            "GET",
            f"{BASE}/api/stream/{home_sid}/proxy",
            params={"detail_path": home_slug, "res": "best"},
            headers={"Range": "bytes=0-1023"},
            timeout=TIMEOUT,
        ) as r:
            first = b""
            for chunk in r.iter_bytes(1024):
                first = chunk
                break
            record(ok(r.status_code in (200, 206) and len(first) > 0,
                      f"status {r.status_code}, {len(first)} bytes"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no sid"))

# ── 15. subtitles VTT ──────────────────────────────────────────────────────
hr("GET /api/stream/{sid}/subtitles/{lang}")
if home_sid and home_slug and captions_lang:
    try:
        r = httpx.get(
            f"{BASE}/api/stream/{home_sid}/subtitles/{captions_lang}",
            params={"detail_path": home_slug},
            timeout=TIMEOUT,
        )
        starts_vtt = r.text.startswith("WEBVTT")
        record(ok(r.status_code == 200 and starts_vtt,
                  f"status {r.status_code}, lang={captions_lang}, WEBVTT={starts_vtt}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))
elif home_sid and home_slug:
    record(ok(True, "no captions to test (skip)"))
else:
    record(ok(False, "no sid"))

# ── 16. tab variants ───────────────────────────────────────────────────────
hr("GET /api/tabs/variants?tab_id=2")
try:
    r = httpx.get(f"{BASE}/api/tabs/variants", params={"tab_id": 2}, timeout=TIMEOUT)
    data = r.json()
    variants = data.get("variants", [])
    record(ok(r.status_code == 200, f"status {r.status_code}, {len(variants)} variants tested"))
    for v in variants:
        if v.get("error"):
            print(f"    {v['variant']:15} ERROR")
            continue
        print(f"    {v['variant']:15} count={v['count']:>2} "
              f"total={v['pager_total']} sentinel={v['sentinel']}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 17. health ─────────────────────────────────────────────────────────────
hr("GET /health")
try:
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    data = r.json()
    record(ok(r.status_code == 200 and data.get("status") == "ok",
              f"version={data.get('version')} tokens_cached={data.get('tokens_cached')} "
              f"indexed={data.get('catalog_indexed')} walk_running={data.get('walk_running')}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 18. frontend ───────────────────────────────────────────────────────────
hr("GET /app  (frontend)")
try:
    r = httpx.get(f"{BASE}/app", timeout=TIMEOUT)
    is_html = r.status_code == 200 and "<html" in r.text.lower() and "MovieBox" in r.text
    record(ok(is_html, f"status {r.status_code}, html={'YES' if is_html else 'NO'}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 19. providers ──────────────────────────────────────────────────────────
hr("GET /providers")
try:
    r = httpx.get(f"{BASE}/providers", timeout=TIMEOUT)
    data = r.json()
    providers_list = data.get("providers", [])
    record(ok(r.status_code == 200 and len(providers_list) > 0,
              f"status {r.status_code}, {data.get('healthy', 0)}/{len(providers_list)} healthy"))
    for p in providers_list:
        state_str = "OK" if p["alive"] and not p["circuit_open"] else ("OPEN" if p["circuit_open"] else "DEAD")
        print(f"    [{state_str:4}] {p['host']:30} latency={p['avg_latency_ms']}ms "
              f"ok={p['total_success']} fail={p['total_failure']}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 20. providers probe ────────────────────────────────────────────────────
hr("POST /providers/probe")
try:
    r = httpx.post(f"{BASE}/providers/probe", timeout=TIMEOUT)
    data = r.json()
    probe_results = data.get("results", [])
    alive = sum(1 for x in probe_results if x.get("alive"))
    record(ok(r.status_code == 200 and len(probe_results) > 0,
              f"status {r.status_code}, {alive}/{len(probe_results)} alive"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 21. legacy hosts ───────────────────────────────────────────────────────
hr("GET /api/hosts")
try:
    r = httpx.get(f"{BASE}/api/hosts", timeout=TIMEOUT)
    data = r.json()
    host_results = data.get("results", [])
    alive = [x for x in host_results if x.get("alive")]
    unique = data.get("unique_catalogs", 0)
    record(ok(r.status_code == 200 and len(host_results) > 0,
              f"status {r.status_code}, {len(alive)}/{len(host_results)} alive, {unique} unique catalogs"))
    for h in host_results:
        status_str = "ALIVE" if h.get("alive") else "DEAD"
        extra = f" latency={h.get('latency_ms', '?')}ms" if h.get("alive") else ""
        print(f"    [{status_str:5}] {h['host']}{extra}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 22. catalog stats by host ──────────────────────────────────────────────
hr("GET /catalog/stats — by_host")
try:
    r = httpx.get(f"{BASE}/catalog/stats", timeout=TIMEOUT)
    data = r.json()
    by_host = data.get("by_host", {})
    record(ok(r.status_code == 200, f"status {r.status_code}, {len(by_host)} hosts in catalog"))
    for host, count in by_host.items():
        print(f"    {host}: {count} subjects")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 23. user bookmarks round-trip ─────────────────────────────────────────
hr("POST /user/bookmarks  →  GET  →  DELETE")
test_slug = "verify-test-bookmark-" + str(int(time.time()))
try:
    r = httpx.post(f"{BASE}/user/bookmarks", json={
        "slug": test_slug, "name": "Verify Test", "poster_url": None,
    }, timeout=TIMEOUT)
    post_ok = r.status_code == 200
    r = httpx.get(f"{BASE}/user/bookmarks", timeout=TIMEOUT)
    data = r.json()
    bookmarks = data.get("bookmarks", [])
    found = any(b.get("slug") == test_slug for b in bookmarks)
    r = httpx.delete(f"{BASE}/user/bookmarks/{test_slug}", timeout=TIMEOUT)
    del_ok = r.status_code == 200
    record(ok(post_ok and found and del_ok,
              f"post={post_ok} found={found} delete={del_ok} count={len(bookmarks)}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 24. user history round-trip ───────────────────────────────────────────
hr("POST /user/history  →  GET  →  DELETE")
test_hist_slug = "verify-test-history-" + str(int(time.time()))
try:
    r = httpx.post(f"{BASE}/user/history", json={
        "slug": test_hist_slug, "se": 1, "ep": 1, "position": 30, "duration": 100,
    }, timeout=TIMEOUT)
    post_ok = r.status_code == 200
    r = httpx.get(f"{BASE}/user/history", timeout=TIMEOUT)
    data = r.json()
    history = data.get("history", [])
    found = any(h.get("slug") == test_hist_slug for h in history)
    r = httpx.delete(f"{BASE}/user/history/{test_hist_slug}", timeout=TIMEOUT)
    del_ok = r.status_code == 200
    record(ok(post_ok and found and del_ok,
              f"post={post_ok} found={found} delete={del_ok} count={len(history)}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 25. recommendations ───────────────────────────────────────────────────
hr("GET /recommendations")
try:
    r = httpx.get(f"{BASE}/recommendations", params={"limit": 10}, timeout=TIMEOUT)
    data = r.json()
    items = data.get("items", [])
    record(ok(r.status_code == 200, f"status {r.status_code}, count={data.get('count')}"))
    if items:
        print(f"    sample: {items[0].get('name')} (rating={items[0].get('rating')}, genres={items[0].get('genre')})")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 26. recommendations/because ───────────────────────────────────────────
hr("GET /recommendations/because/{slug}")
if home_slug:
    try:
        r = httpx.get(f"{BASE}/recommendations/because/{home_slug}", params={"limit": 8}, timeout=TIMEOUT)
        data = r.json()
        items = data.get("items", [])
        record(ok(r.status_code == 200, f"status {r.status_code}, source={data.get('title')}, items={len(items)}"))
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no slug from /home"))

# ── summary ────────────────────────────────────────────────────────────────
hr("SUMMARY")
print(f"  passed: {results['pass']}")
print(f"  failed: {results['fail']}")
sys.exit(0 if results["fail"] == 0 else 1)
