"""
Live verification for MovieBox API Pro.
Chains requests: uses a real slug from /home to test /detail and /api/stream.
Run against a live server: python verify.py [base_url]
"""
import sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TIMEOUT = 30


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
    record(ok(r.status_code == 200 and "<html" in r.text.lower(), f"status {r.status_code}, html present"))
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
    for s in secs:
        items = s.get("items", [])
        print(f"    [{s['section']}] {s['count']} items")
        if items and not home_slug:
            first = items[0]
            home_slug = first.get("slug")
            home_sid = first.get("subject_id")
            print(f"    picked: slug={home_slug} sid={home_sid}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 3. catalogs ────────────────────────────────────────────────────────────
for path in ("/movies", "/tv-series", "/animation"):
    hr(f"GET {path}")
    try:
        r = httpx.get(f"{BASE}{path}", timeout=TIMEOUT)
        data = r.json()
        items = data.get("items", [])
        record(ok(r.status_code == 200 and len(items) > 0,
                  f"status {r.status_code}, page={data.get('page')}, total={data.get('total')}"))
        sample_items(items, path)
    except Exception as e:
        record(ok(False, f"exception: {e}"))

# ── 4. search ──────────────────────────────────────────────────────────────
hr("GET /search?q=matrix")
try:
    r = httpx.get(f"{BASE}/search", params={"q": "matrix"}, timeout=TIMEOUT)
    data = r.json()
    items = data.get("items", [])
    record(ok(r.status_code == 200, f"status {r.status_code}, {len(items)} results, total={data.get('total')}"))
    sample_items(items, "search")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 5. suggest ─────────────────────────────────────────────────────────────
hr("GET /search/suggest?q=break")
try:
    r = httpx.get(f"{BASE}/search/suggest", params={"q": "break"}, timeout=TIMEOUT)
    data = r.json()
    sugg = data.get("suggestions", [])
    record(ok(r.status_code == 200, f"status {r.status_code}, {len(sugg)} suggestions"))
    if sugg:
        print(f"    sample: {sugg[0]}")
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── 6. detail ──────────────────────────────────────────────────────────────
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
    record(ok(False, "no slug from /home to test with"))

# ── 7. stream ──────────────────────────────────────────────────────────────
hr("GET /api/stream/{sid}")
if home_sid and home_slug:
    try:
        r = httpx.get(
            f"{BASE}/api/stream/{home_sid}",
            params={"detail_path": home_slug},
            timeout=TIMEOUT,
        )
        data = r.json()
        has = data.get("has_resource")
        srcs = data.get("sources", [])
        record(ok(r.status_code == 200, f"status {r.status_code}, has_resource={has}, sources={len(srcs)}"))
        for s in srcs[:3]:
            print(f"    {s.get('resolution')} {s.get('format')} codec={s.get('codec')} url={'YES' if s.get('url') else 'NO'}")
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no subject_id from /home to test with"))

# ── 8. captions ────────────────────────────────────────────────────────────
hr("GET /api/stream/{sid}/captions")
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
            print(f"    first: {caps[0]}")
    except Exception as e:
        record(ok(False, f"exception: {e}"))
else:
    record(ok(False, "no subject_id from /home to test with"))

# ── 9. health ──────────────────────────────────────────────────────────────
hr("GET /health")
try:
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    data = r.json()
    record(ok(r.status_code == 200 and data.get("status") == "ok", f"{data}"))
except Exception as e:
    record(ok(False, f"exception: {e}"))

# ── summary ────────────────────────────────────────────────────────────────
hr("SUMMARY")
print(f"  passed: {results['pass']}")
print(f"  failed: {results['fail']}")
sys.exit(0 if results["fail"] == 0 else 1)