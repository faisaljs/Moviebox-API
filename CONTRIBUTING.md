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

Requires Python 3.10+ (union type syntax in the codebase).

Server comes up on `http://127.0.0.1:8000`. Three entry points:

- `/` — the app (hero carousel, catalog, player, bookmarks, history)
- `/dashboard` — operator console (provider health, diagnostics, live stream debug)
- `/docs` — Swagger UI

```bash
# autoreload for dev
RELOAD=1 python main.py
```

No first-boot walk. The app is stateless — every route fetches from upstream on demand. First `/home` call triggers token harvest; first `/api/stream` call triggers player-domain discovery. Both cached in-process, both die with the process.

## Before you open a PR

1. **Run the verifier.** With the server live:

   ```bash
   python verify.py
   ```

   Every check must print `[PASS]`. If one fails, either your change broke it or upstream drifted — figure out which before opening the PR. `verify.py` exits 2 if the server is unreachable (that's the fast-fail), 1 on any check failure, 0 on clean pass.

2. **Touch the smallest surface possible.** One concern per PR. Don't bundle a refactor with a feature.

3. **No new dependencies** unless there's a real reason. This project is fastapi + httpx + uvicorn + python-dotenv. That's it. Adding an SDK, an ORM, a config framework, a logging lib — those need justification in the PR body. Nine times out of ten the stdlib covers it.

4. **Don't reformat untouched code.** Diffs should be reviewable in under a minute.

5. **No new server-side state.** The backend is stateless by design. If your change wants to persist something across requests, put it in the browser (localStorage) or argue hard in the PR body for why it can't be. Caches in `state.py` are fine — they're ephemeral and die with the process. A database, a message queue, a Redis instance — no.

## What lands

- Bug fixes against upstream API changes
- New endpoints that map to real BFF routes (find them in the web player's network tab)
- Response shape improvements — cleaner field names, more complete data extraction
- Caching, connection pooling, retry logic that measurably reduces upstream calls
- Better error messages when upstream returns something weird
- Docker / deployment improvements
- Frontend polish that doesn't break the vanilla-JS constraint (no build step, no deps)
- New views, keyboard shortcuts, UI polish in `app.html` or `api_dashboard.html`

## What doesn't

- **SQLite, ORMs, any persistence layer.** That was 2.9.0. It's gone. The stateless rewrite is deliberate.
- **Server-side user state.** Bookmarks, history, recommendations — all client-side. PRs that add `/user/*` endpoints back will be closed.
- Auth-bypass tricks, scraping fallbacks, "when the API fails, load the HTML instead" — the whole point is pure API
- Anything that adds an external service dependency (Redis, Postgres, a managed queue)
- Rewrites of the module structure without a concrete problem being solved
- Tests that hit live upstream in CI (see below)
- React / Vue / Svelte / any frontend framework — the frontend is intentionally two single HTML files

## Module layout

Understand these core modules before changing shared behavior:

```
config.py            env vars, headers, constants — no imports from local modules
state.py             mutable globals (client, tokens, caches, probe_task)
providers.py         provider health, circuit breaker, probe loop
upstream.py          token cache, bff_request (failover), player, stream resolution
helpers.py           normalize, srt_to_vtt, pick_mp4_stream
env_loader.py        .env file discovery
routes/              API endpoints grouped by feature
main.py              FastAPI app + lifespan + UI routes
app.html             user-facing frontend
api_dashboard.html   operator console
```

**Import order (no circular imports):**

```
config → state → providers → upstream → routes → main
```

`helpers` and `env_loader` are leaf modules.

**The rule:** `import state` and `import providers` — never `from state import client`. Mutable references must stay live. If you `from state import client`, you get a frozen copy and the lifespan updates won't reach your code.

## Three things upstream does that will bite you

Every upstream drift I've had to fix fell into one of these three buckets. Check them first when something breaks.

### 1. Token harvest is header-sensitive

`_fetch_token` in `upstream.py` uses **only** `User-Agent` and `Referer`. Adding `sec-fetch-site: cross-site`, `sec-fetch-mode: cors`, `Origin`, or `X-Client-Info` makes upstream return 200 with no `x-user` header — silent fail. That's why the harvest uses minimal headers while every other route uses `DEFAULT_HEADERS`.

**And it uses a fresh `httpx.AsyncClient` per call.** The shared client accumulates `set-cookie: token=` from the probe loop and prior `/home` calls. Once it has a stale cookie, upstream returns 200 without `x-user`. The fresh client guarantees a clean session.

If a route that needs a token stops working with `tokens_cached: 0` in `/health`, the harvest is broken. Hit `POST /debug/fetch-token` and check the server log for `[fetch_token]` lines.

### 2. Stale tokens return 400, not 401

Upstream returns `{"code": 400, "message": "invalid token"}` for expired tokens. `_attempt` parses the response body, detects `"invalid token"` in the message, drops the cached token, harvests a fresh one, and retries once. If you see the retry path firing on a status code we don't expect, add it to the `is_auth_fail` check in `_attempt`.

### 3. The player domain is a static OSS frontend

`/media-player/get-domain` returns something like `https://mzfi.me`. That's **not** an API host — it serves HTML from Aliyun OSS. The `/wefeed-h5api-bff/subject/play` endpoint stayed on `API_BASE`. The player domain is only used to build the `Referer` header so upstream treats the request as coming from a legitimate player.

If streams stop working and `/debug/play` returns a domain but no streams, check whether `/subject/play` on that domain returns HTML (static 404) instead of JSON. If it does, upstream moved the API again — find it in the browser DevTools.

## Debugging upstream changes

The BFF is undocumented and can shift without warning. When a route breaks:

1. Open `moviebox.ph` in a browser, DevTools → Network → filter `wefeed-h5api-bff`
2. Click around until you see the request your endpoint is wrapping
3. Compare headers, params, and payload shape to what `upstream.py` sends
4. Update `DEFAULT_HEADERS` / `PLAYER_HEADERS` / payload keys to match

The three flows above are where 90% of upstream changes land. Check those first before digging into a specific route.

**Home feed is geo-targeted.** Mumbai sees `Cinema`, `Bollywood`, `Top Anime`. Singapore sees `Popular Movie`, `K-Drama`, `Anime[English Dubbed]`. The `/movies`, `/tv-series`, `/animation` routes use substring matching against `config.py::CATALOG_SECTIONS` so both work. If a category returns empty, check `/sections` first — the keyword list might not match the current region's section names.

**`/subject/filter` requires auth we don't have as guests.** All nine payload variants sentinel at `pager.totalCount >= 1000000`. `/api/tabs/variants` shows this. That's why `/movies` and friends fall back to home sections instead of the filter endpoint.

## Code style

- Type hints on function signatures
- `(x or {}).get("y")` for defensive navigation — the BFF sends `null` where you'd expect an object
- Comments only where the reasoning isn't obvious from the code. "Send the request" is noise. "Upstream refreshes the JWT on every response that carries an x-user header" is signal.
- Async everywhere. No blocking `httpx.get` in a route.
- Route handlers stay thin. Shared logic goes into helper functions.
- **Never** `from state import client` — always `import state` then `state.client`
- **Never** hardcode a domain. `API_BASE` for the BFF, `get_player_domain()` for the player page, `state.domain_cache` to avoid the extra call.
- **Never** put state that needs to survive a restart on the server. That's what localStorage is for.

## Frontend guidelines

`app.html` and `api_dashboard.html` are single-file vanilla JS. No build step, no npm, no bundler, no framework. If you want to add something that feels like it needs React, it probably fits in 200 lines of vanilla JS with `document.createElement`.

Constraints:

- No external JS libraries
- No external CSS frameworks
- Inline `<style>` and `<script>` only — no `<link rel="stylesheet">` to a CDN
- localStorage for persistence — keys are namespaced `mb.*` and listed in README
- Same-origin fetches only — no CORS, no `fetch` to third parties

Things that are encouraged:

- Keyboard shortcuts (currently: `/` focuses search, `Esc` closes player, arrow keys / `f` / `m` in player)
- Skeleton loaders (every fetch shows one)
- Lazy image loading (`loading="lazy"` + fade-in on `onload`)
- Accessibility (`aria-label` on icon buttons, `type="button"` on non-submit buttons)

## Testing

There's no unit test suite. The API surface is a thin proxy — unit tests would just re-assert dict shapes and rot the moment upstream shifts. `verify.py` is the integration test.

`verify.py` does:

- Fast-fails with exit 2 if the server is unreachable (5s timeout on `/health`)
- Picks the search fixture with the most stream sources among the top-5 results
- Validates byte-level MP4 signature on the proxy (`ftyp` box at offset 4)
- Verifies WEBVTT prefix on subtitle conversion (not just a 200 check)
- Verifies enriched suggestions return non-null slugs (proves enrichment end-to-end)

If you want to add automated tests, they need to be:

- Against a recorded upstream fixture (VCR-style), not live
- Run in CI without network access
- Small — cover `_get_category_data` parsing, `/home` section extraction, `srt_to_vtt`, `pick_mp4_stream`, `matchesLanguage` logic, not the whole request path

## Commit messages

Plain English, present tense, one line. Body if the change isn't self-evident.

```
fix: handle null cover on /home banner items
add: /health endpoint for token + domain cache state
refactor: extract player referer builder
fix: retry token harvest on 400 invalid-token, not just 401
add: language filter to header, persisted in localStorage
```

No `feat(scope):`, no emoji, no `[JIRA-123]` prefixes.

## Pull requests

PR body should answer:

- What changed
- Why (link to upstream behavior, an issue, or a repro)
- How you verified it

If `verify.py` output changed, paste it. If it's a behavioral change, describe the before/after response shape. If it's a frontend change, include a screenshot or a 10-second clip — most reviewers won't run the change locally for a CSS tweak.

## Reporting upstream breakage

If a route stops working and you're not fixing it yourself: open an issue with

- The route
- The status code / error body you get
- The output of `GET /health` and `GET /providers` (both drop tokens, both are cheap)
- The equivalent request in the browser DevTools that still works
- Which region your instance is in (`/sections` output helps)

That's usually enough to diff and fix in one pass. Nine times out of ten the answer is "token harvest broke" or "player domain moved" and both are one-line fixes once you can see the diff.

## One last thing

If you're going to run this on a public URL — even briefly — put `auth_basic` in front of it from day one. **Also remove or gate the `/debug/*` endpoints** — `/debug/fetch-token` writes to the token cache and `/debug/play` signs upstream requests with the app's token. Fine on `127.0.0.1`; not fine exposed.

Not for security (it's a personal tool), for cover. A public streaming proxy on your own domain on AWS Lightsail is one DMCA notice from losing both the instance and the account. Personal use, `http://127.0.0.1:8000/`, is fine. That's the whole threat model.