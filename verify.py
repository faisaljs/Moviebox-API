#!/usr/bin/env python3
"""
Live verification for MovieBox API Pro.

Author: Faisal (https://github.com/faisaljs)
Repo:   https://github.com/faisaljs/Moviebox-API
License: MIT

Run against a live server: python verify.py [base_url]
Default: http://127.0.0.1:8000

Exits 0 on all pass, 1 on any fail, 2 if the server is unreachable.
Skips (no slug, no captions, etc.) don't count as failures — they're just
"upstream didn't give us enough to test".

Fixture picking: probes the top 5 search results and uses whichever has the
most stream sources, so the proxy/caption/subtitle tests run against a
title that can actually exercise them. Cached by upstream.resolve_stream
for 30s, so the extra probes don't cost the later stream call.
"""

import sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TIMEOUT = 90

# Fast-fail: if /health doesn't respond, the rest is noise.
try:
    httpx.get(f"{BASE}/health", timeout=5)
except httpx.RequestError as e:
    print(f"FATAL: {BASE} unreachable ({type(e).__name__})")
    print("Hint: is the app running? Start it with `python main.py`.")
    sys.exit(2)

results = {"pass": 0, "fail": 0, "skip": 0}


def hr(label):
    print(f"\n{'─' * 60}\n{label}\n{'─' * 60}")


def check(cond, msg):
    if cond:
        print(f"  [PASS] {msg}")
        results["pass"] += 1
    else:
        print(f"  [FAIL] {msg}")
        results["fail"] += 1
    return cond


def skip(msg):
    print(f"  [SKIP] {msg}")
    results["skip"] += 1


# ── 1. /health ──────────────────────────────────────────────────────────────
hr("GET /health")
try:
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(d.get("status") == "ok", f"status field: {d.get('status')}")
    check(bool(d.get("version")), f"version: {d.get('version')}")
    provs = d.get("providers", {})
    check(len(provs) > 0, f"{len(provs)} providers tracked")
    print(f"    tokens_cached: {d.get('tokens_cached')}, domain: {d.get('domain_cached')}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 2. /providers ───────────────────────────────────────────────────────────
hr("GET /providers")
try:
    r = httpx.get(f"{BASE}/providers", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    provs = d.get("providers", [])
    check(len(provs) > 0, f"{len(provs)} providers, {d.get('healthy', 0)} healthy")
    for p in provs:
        state_str = "OK" if p["alive"] and not p["circuit_open"] else ("OPEN" if p["circuit_open"] else "DEAD")
        print(f"    [{state_str:4}] {p['host']:30} latency={p['avg_latency_ms']}ms fails={p['consecutive_failures']}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 3. /providers/probe ─────────────────────────────────────────────────────
hr("POST /providers/probe")
try:
    r = httpx.post(f"{BASE}/providers/probe", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    results_list = d.get("results", [])
    alive = sum(1 for x in results_list if x.get("alive"))
    check(len(results_list) > 0, f"{alive}/{len(results_list)} alive")
except Exception as e:
    check(False, f"exception: {e}")


# ── 4. /api/hosts (legacy) ──────────────────────────────────────────────────
hr("GET /api/hosts")
try:
    r = httpx.get(f"{BASE}/api/hosts", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check("primary" in d, f"primary: {d.get('primary')}")
    check(len(d.get("results", [])) > 0, f"{len(d.get('results', []))} hosts")
except Exception as e:
    check(False, f"exception: {e}")


# ── 5. /home ────────────────────────────────────────────────────────────────
hr("GET /home")
home_slug = None
home_sid = None
try:
    r = httpx.get(f"{BASE}/home", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    secs = d.get("sections", [])
    check(len(secs) > 0, f"{len(secs)} sections")
    for s in secs[:3]:
        print(f"    [{s['section']}] {s['count']} items")
    for s in secs:
        if s.get("section") == "Banner":
            continue
        if s.get("count", 0) > 0 and s.get("items"):
            first = s["items"][0]
            home_slug = first.get("slug")
            home_sid = first.get("subject_id")
            print(f"    picked: {first.get('name')} (slug={home_slug})")
            break
    check(home_slug is not None, "found a subject to test with")
except Exception as e:
    check(False, f"exception: {e}")


# ── 6. /home/all ────────────────────────────────────────────────────────────
hr("GET /home/all")
try:
    r = httpx.get(f"{BASE}/home/all", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(d.get("count", 0) > 0, f"{d.get('count')} deduped items")
except Exception as e:
    check(False, f"exception: {e}")


# ── 7. /sections ────────────────────────────────────────────────────────────
hr("GET /sections")
try:
    r = httpx.get(f"{BASE}/sections", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(len(d.get("sections", [])) > 0, f"{len(d.get('sections', []))} sections")
except Exception as e:
    check(False, f"exception: {e}")


# ── 8. /browse/{section} ────────────────────────────────────────────────────
hr("GET /browse/Cinema")
try:
    r = httpx.get(f"{BASE}/browse/Cinema", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}, total={d.get('total')}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 9. /movies, /tv-series, /animation ──────────────────────────────────────
for path in ("/movies", "/tv-series", "/animation"):
    hr(f"GET {path}")
    try:
        r = httpx.get(f"{BASE}{path}", timeout=TIMEOUT)
        d = r.json()
        check(r.status_code == 200, f"status {r.status_code}, source={d.get('source')}, items={len(d.get('items', []))}")
    except Exception as e:
        check(False, f"exception: {e}")


# ── 10. /search ─────────────────────────────────────────────────────────────
hr("GET /search?q=matrix")
matrix_slug = None
matrix_sid = None
try:
    r = httpx.get(f"{BASE}/search", params={"q": "matrix"}, timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(d.get("total", 0) > 0, f"total: {d.get('total')}")
    items = d.get("items", [])
    if items:
        first = items[0]
        matrix_slug = first.get("slug")
        matrix_sid = first.get("subject_id")
        print(f"    first: {first.get('name')}")
        print(f"    slug:  {matrix_slug}")
        check(matrix_slug is not None, "slug present on first result")
except Exception as e:
    check(False, f"exception: {e}")


# ── 10b. Fixture picking: probe top-5 search results, use max-sources one ──
if matrix_slug and matrix_sid:
    hr("Picking fixture (max sources among top-5)")
    candidates = [(i.get("slug"), i.get("subject_id")) for i in items[:5] if i.get("slug") and i.get("subject_id")]
    best_sid, best_slug, best_count, best_res = None, None, 0, []
    for cand_slug, cand_sid in candidates:
        try:
            probe = httpx.get(
                f"{BASE}/api/stream/{cand_sid}",
                params={"detail_path": cand_slug, "se": 0, "ep": 0},
                timeout=15,
            ).json()
            count = len(probe.get("sources", []))
            resolutions = [s["resolution"] for s in probe.get("sources", [])]
            print(f"    {cand_slug[:50]:50} {count} sources {resolutions}")
            if count > best_count:
                best_count = count
                best_sid, best_slug, best_res = cand_sid, cand_slug, resolutions
        except Exception as e:
            print(f"    {cand_slug[:50]:50} probe failed: {e}")
    if best_sid:
        matrix_sid, matrix_slug = best_sid, best_slug
        check(True, f"fixture pick: {best_slug} ({best_count} sources, {best_res})")
    else:
        check(False, "no candidate had stream sources")
else:
    skip("no search results to pick from")


# ── 11. /search/suggest?enrich=true ─────────────────────────────────────────
hr("GET /search/suggest?q=break&enrich=true")
try:
    r = httpx.get(f"{BASE}/search/suggest",
                  params={"q": "break", "enrich": "true"}, timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    sugs = d.get("suggestions", [])
    check(len(sugs) > 0, f"{len(sugs)} suggestions")
    with_slug = sum(1 for s in sugs if s.get("slug"))
    check(with_slug > 0, f"{with_slug}/{len(sugs)} enriched with slug")
except Exception as e:
    check(False, f"exception: {e}")


# ── 12. /detail/{slug} ──────────────────────────────────────────────────────
hr("GET /detail/{slug}")
if matrix_slug:
    try:
        r = httpx.get(f"{BASE}/detail/{matrix_slug}", timeout=TIMEOUT)
        d = r.json()
        inner = d.get("data", {}) or {}
        check(r.status_code == 200 and bool(inner),
              f"status {r.status_code}, keys: {list(inner.keys())[:6]}")
    except Exception as e:
        check(False, f"exception: {e}")
elif home_slug:
    try:
        r = httpx.get(f"{BASE}/detail/{home_slug}", timeout=TIMEOUT)
        d = r.json()
        inner = d.get("data", {}) or {}
        check(r.status_code == 200 and bool(inner),
              f"status {r.status_code}, keys: {list(inner.keys())[:6]}")
    except Exception as e:
        check(False, f"exception: {e}")
else:
    skip("no slug")


# ── 13. /api/stream/{sid} ───────────────────────────────────────────────────
stream_sid = matrix_sid or home_sid
stream_slug = matrix_slug or home_slug
hr("GET /api/stream/{sid}")
stream_ok = False
sources = []
if stream_sid and stream_slug:
    try:
        r = httpx.get(f"{BASE}/api/stream/{stream_sid}",
                      params={"detail_path": stream_slug, "se": 0, "ep": 0},
                      timeout=TIMEOUT)
        d = r.json()
        check(r.status_code == 200, f"status {r.status_code}")
        check(d.get("has_resource") is not None, f"has_resource: {d.get('has_resource')}")
        sources = d.get("sources", [])
        stream_ok = bool(d.get("has_resource")) and len(sources) > 0
        check(stream_ok, f"{len(sources)} sources: {[s['resolution'] for s in sources]}")
    except Exception as e:
        check(False, f"exception: {e}")
else:
    skip("no sid/slug")


# ── 14. /api/stream/{sid}/captions ──────────────────────────────────────────
hr("GET /api/stream/{sid}/captions")
captions_lang = None
if stream_sid and stream_slug:
    try:
        r = httpx.get(f"{BASE}/api/stream/{stream_sid}/captions",
                      params={"detail_path": stream_slug, "se": 0, "ep": 0},
                      timeout=TIMEOUT)
        d = r.json()
        check(r.status_code == 200, f"status {r.status_code}")
        caps = d.get("captions", [])
        check(isinstance(caps, list), f"{len(caps)} caption tracks")
        if caps:
            captions_lang = caps[0].get("lan")
            print(f"    first: {caps[0].get('lanName')} ({captions_lang})")
    except Exception as e:
        check(False, f"exception: {e}")
else:
    skip("no sid")


# ── 15. /api/stream/{sid}/proxy (Range + byte signature) ────────────────────
hr("GET /api/stream/{sid}/proxy  (Range: bytes=0-1048575)")
if stream_ok:
    try:
        with httpx.stream(
            "GET",
            f"{BASE}/api/stream/{stream_sid}/proxy",
            params={"detail_path": stream_slug, "se": 0, "ep": 0, "res": "best"},
            headers={"Range": "bytes=0-1048575"},
            timeout=TIMEOUT,
        ) as r:
            first = b""
            total = 0
            for chunk in r.iter_bytes(65536):
                if not first:
                    first = chunk[:16]
                total += len(chunk)
                if total >= 1048576:
                    break
            check(r.status_code in (200, 206), f"status {r.status_code}, {total} bytes")
            check(total >= 1048576, f"received at least 1MB")
            # MP4 first box: [size:4][type:4] where type == b"ftyp"
            is_mp4 = len(first) >= 8 and first[4:8] == b"ftyp"
            check(is_mp4, f"first bytes look like MP4 (hex={first[:12].hex()})")
    except Exception as e:
        check(False, f"exception: {e}")
else:
    skip("no stream sources")


# ── 16. /api/stream/{sid}/subtitles/{lang} ──────────────────────────────────
hr("GET /api/stream/{sid}/subtitles/{lang}")
if stream_sid and stream_slug and captions_lang:
    try:
        r = httpx.get(f"{BASE}/api/stream/{stream_sid}/subtitles/{captions_lang}",
                      params={"detail_path": stream_slug, "se": 0, "ep": 0},
                      timeout=TIMEOUT)
        starts_vtt = r.text.startswith("WEBVTT")
        check(r.status_code == 200 and starts_vtt,
              f"status {r.status_code}, lang={captions_lang}, WEBVTT={starts_vtt}, {len(r.text)} bytes")
    except Exception as e:
        check(False, f"exception: {e}")
elif stream_sid and stream_slug:
    skip("no captions to test")
else:
    skip("no sid")


# ── 17. /api/tabs ──────────────────────────────────────────────────────────
hr("GET /api/tabs?min_id=2&max_id=3")
try:
    r = httpx.get(f"{BASE}/api/tabs",
                  params={"min_id": 2, "max_id": 3, "per_page": 1}, timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(len(d.get("results", [])) == 2, f"{len(d.get('results', []))} tab results")
except Exception as e:
    check(False, f"exception: {e}")


# ── 18. /api/tabs/variants ─────────────────────────────────────────────────
hr("GET /api/tabs/variants?tab_id=2")
try:
    r = httpx.get(f"{BASE}/api/tabs/variants",
                  params={"tab_id": 2}, timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    variants = d.get("variants", [])
    check(len(variants) > 0, f"{len(variants)} variants tested")
    for v in variants:
        if v.get("error"):
            print(f"    {v['variant']:15} ERROR")
        else:
            print(f"    {v['variant']:15} count={v['count']:>2} sentinel={v['sentinel']}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 19. /api/debug/upstream ────────────────────────────────────────────────
hr("GET /api/debug/upstream")
try:
    r = httpx.get(f"{BASE}/api/debug/upstream",
                  params={"path": "/home", "method": "GET"}, timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check("code" in d or "data" in d, f"keys: {list(d.keys())[:4]}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 20. /debug/tokens ──────────────────────────────────────────────────────
hr("GET /debug/tokens")
try:
    r = httpx.get(f"{BASE}/debug/tokens", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check("count" in d, f"cached tokens: {d.get('count')}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 21. /debug/fetch-token ─────────────────────────────────────────────────
hr("POST /debug/fetch-token")
try:
    r = httpx.post(f"{BASE}/debug/fetch-token", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200, f"status {r.status_code}")
    check(d.get("success") is True, f"harvest success, len={d.get('length')}")
except Exception as e:
    check(False, f"exception: {e}")


# ── 22. /debug/play ────────────────────────────────────────────────────────
hr("POST /debug/play")
if stream_sid and stream_slug:
    try:
        r = httpx.post(f"{BASE}/debug/play",
                       params={"subject_id": stream_sid, "detail_path": stream_slug, "se": 0, "ep": 0},
                       timeout=TIMEOUT)
        d = r.json()
        check(r.status_code == 200, f"status {r.status_code}")
        check("error" not in d, f"hasResource: {d.get('hasResource')}, streams: {d.get('streams')}")
    except Exception as e:
        check(False, f"exception: {e}")
else:
    skip("no sid")


# ── 23. /docs, /openapi.json ───────────────────────────────────────────────
hr("GET /docs  and  /openapi.json")
try:
    r = httpx.get(f"{BASE}/docs", timeout=TIMEOUT)
    check(r.status_code == 200 and "<!doctype" in r.text.lower(),
          f"/docs status {r.status_code}")
    r = httpx.get(f"{BASE}/openapi.json", timeout=TIMEOUT)
    d = r.json()
    check(r.status_code == 200 and "paths" in d,
          f"/openapi.json status {r.status_code}, {len(d.get('paths', {}))} paths")
except Exception as e:
    check(False, f"exception: {e}")


# ── summary ────────────────────────────────────────────────────────────────
hr("SUMMARY")
total = results["pass"] + results["fail"] + results["skip"]
print(f"  total:   {total}")
print(f"  passed:  {results['pass']}")
print(f"  failed:  {results['fail']}")
print(f"  skipped: {results['skip']}")
sys.exit(0 if results["fail"] == 0 else 1)