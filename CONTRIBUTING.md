# Contributing

**Maintainer:** [Faisal (@faisaljs)](https://github.com/faisaljs) · [Repo](https://github.com/faisaljs/Moviebox-API) · [Issues](https://github.com/faisaljs/Moviebox-API/issues)

Short version: fork, branch, make it work, run `verify.py`, open a PR. Keep it small. Explain _why_ in the PR body, not _what_ — the diff shows what.

## Setup

```bash
git clone https://github.com/faisaljs/Moviebox-API
cd Moviebox-API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Server comes up on `http://localhost:8000`. Two entry points:

- `/` — HTML dashboard listing every endpoint with test buttons
- `/app` — the actual frontend (hero carousel, catalog, player, bookmarks, history)

```bash
# autoreload for dev
RELOAD=1 python main.py
```

The first boot kicks off the catalog walk. ~3 minutes to populate the DB, then enrichment runs. Watch progress at `/catalog/stats`.

## Before you open a PR

1. **Run the verifier.** With the server live:

   ```bash
   python verify.py
   ```

   Every check must print `[PASS]`. If one fails, either your change broke it or upstream drifted — figure out which before opening the PR.

2. **Touch the smallest surface possible.** One concern per PR. Don't bundle a refactor with a feature.

3. **No new dependencies** unless there's a real reason. This project is fastapi + httpx + uvicorn. Adding an SDK, an ORM, a config framework, a logging lib — those need justification in the PR body. Nine times out of ten the stdlib covers it.

4. **Don't reformat untouched code.** Diffs should be reviewable in under a minute.

5. **Stop the server before touching `catalog.db`.** Two `python main.py` processes against one SQLite file will corrupt it. If you're iterating on schema changes:
   ```bash
   # stop server, confirm nothing holding the DB
   lsof catalog.db 2>/dev/null || echo "clear"
   # delete and restart clean
   rm -f catalog.db catalog.db-wal catalog.db-shm
   python main.py
   ```

## What lands

- Bug fixes against upstream API changes
- New endpoints that map to real BFF routes (find them in the web player's network tab)
- Response shape improvements — cleaner field names, more complete data extraction
- Caching, connection pooling, retry logic that measurably reduces upstream calls
- Better error messages when upstream returns something weird
- Docker / deployment improvements
- Frontend polish that doesn't break the vanilla-JS constraint (no build step, no deps)

## What doesn't

- Auth-bypass tricks, scraping fallbacks, "when the API fails, load the HTML instead" — the whole point is pure API
- Anything that adds an external service dependency (Redis, Postgres, a managed queue)
- Rewrites of the module structure without a concrete problem being solved
- Tests that hit live upstream in CI (see below)
- React / Vue / Svelte / any frontend framework — the frontend is intentionally a single HTML file

## Module layout

Understand these core modules before changing shared behavior:

```
config.py            env vars, headers, constants — no imports from local modules
state.py             mutable globals (client, db, tokens, caches, walk_state)
providers.py         provider health, circuit breaker, probe loop
upstream.py          token cache, bff_request (failover), player resolution
storage.py           sqlite schema, FTS5, read, upsert
helpers.py           normalize, srt_to_vtt, pick_mp4_stream
catalog_worker.py    walk, enrichment, maintenance loop
dashboard.py         DASHBOARD_HTML string
routes/              API endpoints grouped by feature
main.py              FastAPI app + lifespan + static routes
```

**Import order (no circular imports):**

```
config → state → providers → upstream → catalog_worker → routes → main
```

`storage` and `helpers` are leaf modules — nothing local imports them except the modules that need them.

**The rule:** `import state` and `import providers` — never `from state import client`. Mutable references must stay live. If you `from state import client`, you get a frozen copy and the lifespan updates won't reach your code.

## Debugging upstream changes

The BFF is undocumented and can shift without warning. When a route breaks:

1. Open `moviebox.ph` in a browser, DevTools → Network → filter `wefeed-h5api-bff`
2. Click around until you see the request your endpoint is wrapping
3. Compare headers, params, and payload shape to what `upstream.py` sends
4. Update `DEFAULT_HEADERS` / `PLAYER_HEADERS` / payload keys to match

The token flow (`x-user` header → per-host cache), the player-domain flow (`/media-player/get-domain` → 300s cache), and the provider failover are the three places upstream changes will hit first. Check those before digging into a specific route.

**Home feed is geo-targeted.** Mumbai sees `Cinema`, `Bollywood`, `Top Anime`. Singapore sees `Popular Movie`, `K-Drama`, `Anime[English Dubbed]`. If catalog counts look wrong, check `/sections` first — the classifier's keyword list in `config.py::CATALOG_SECTIONS` might not match the current region's section names.

## Code style

- Type hints on function signatures
- `(x or {}).get("y")` for defensive navigation — the BFF sends `null` where you'd expect an object
- Comments only where the reasoning isn't obvious from the code. "Send the request" is noise. "Upstream refreshes the JWT on every response that carries an x-user header" is signal.
- Async everywhere. No blocking `httpx.get` in a route.
- Route handlers stay thin. Shared logic goes into helper functions.
- **Never** `from state import client` — always `import state` then `state.client`
- **Never** call `sqlite3.connect()` directly in a route — use `storage.read()` / `storage.read_scalar()`

## Testing

There's no unit test suite. The API surface is a thin proxy — unit tests would just re-assert dict shapes and rot the moment upstream shifts. `verify.py` is the integration test.

If you want to add automated tests, they need to be:

- Against a recorded upstream fixture (VCR-style), not live
- Run in CI without network access
- Small — cover `_get_category_data` parsing, `/home` section extraction, `srt_to_vtt`, and `pick_mp4_stream` logic, not the whole request path

## Commit messages

Plain English, present tense, one line. Body if the change isn't self-evident.

```
fix: handle null cover on /home banner items
add: /health endpoint for token + domain cache state
refactor: extract player referer builder
add: FTS5 catalog search with LIKE fallback
```

No `feat(scope):`, no emoji, no `[JIRA-123]` prefixes.

## Pull requests

PR body should answer:

- What changed
- Why (link to upstream behavior, an issue, or a repro)
- How you verified it

If `verify.py` output changed, paste it. If it's a behavioral change, describe the before/after response shape.

## Reporting upstream breakage

If a route stops working and you're not fixing it yourself: open an issue with

- The route
- The status code / error body you get
- The equivalent request in the browser DevTools that still works
- Which region your instance is in (`/sections` output helps)

That's usually enough to diff and fix in one pass.

## One last thing

If you're going to run this on a public URL — even briefly — put `auth_basic` in front of it from day one. Not for security (it's a personal tool), for cover. A public streaming proxy on your own domain on AWS Lightsail is one DMCA notice from losing both the instance and the account. Personal use, `http://localhost:8000/app`, is fine. That's the whole threat model.
