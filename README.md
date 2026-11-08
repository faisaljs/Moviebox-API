<p align="center">
  <img src="https://h5-static.aoneroom.com/ssrStatic/mbOfficial/public/_nuxt/web-logo.apJjVir2.svg" alt="LOGO" width="200"/>
</p>

<p align="center">
  <a href="https://github.com/faisaljs/Moviebox-API"><img alt="GitHub Repo" src="https://img.shields.io/badge/github-faisaljs%2FMoviebox--API-ff3d71?style=flat-square&logo=github"></a>
  <a href="https://github.com/faisaljs"><img alt="Author" src="https://img.shields.io/badge/author-faisaljs-3366ff?style=flat-square"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-00c853?style=flat-square"></a>
  <a href="https://github.com/faisaljs/Moviebox-API/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/faisaljs/Moviebox-API?style=flat-square&color=ffcc00"></a>
</p>

# MovieBox API Pro

A pure REST API wrapper around [moviebox.ph](https://moviebox.ph) with a self-hosted frontend, provider failover, and no database.

No scraping. No HTML parsing. No headless browser. It talks the exact same private JSON API the moviebox web player talks — `h5-api.aoneroom.com/wefeed-h5api-bff` — and re-exposes it as a clean REST surface plus a browser UI.

Every route proxies upstream on demand. The only in-process state is the token cache, player-domain cache, home-feed cache (bounded, 5-minute TTL), stream-resolution cache (30s TTL), and the provider circuit-breaker registry. Kill the process and all of it evaporates.

**Version 2.9.1** — stateless rewrite. No database, no CLI, no server-side user state. Bookmarks and watch history live in the browser.

---

## What it does

- **Discovery** — banners, featured blocks, and every category row from the moviebox home feed
- **Search** — full-text search + typeahead suggestions against upstream
- **Metadata** — full detail tree for any subject (episodes, seasons, languages, cast, trailer, artwork)
- **Streams** — direct MP4 sources per resolution, plus HLS and DASH manifests
- **Stream proxy** — Range-aware MP4 passthrough for media servers
- **Subtitles** — full caption list per episode, SRT→VTT conversion inline
- **Provider failover** — 7 known mirrors, circuit breaker per host, automatic fallover
- **Web frontend** — hero carousel, catalog browser, player with resume / quality / subtitle / episode navigation, trailer playback, continue-watching, bookmarks, watch history — all client-side
- **Operator dashboard** — separate console for provider health, tab diagnostics, raw upstream probing
- **Diagnostics** — tab-ID probing, payload variant testing, raw upstream passthrough, health

## What it isn't

- Not a proxy for HLS/DASH manifests (MP4 only)
- Not a downloader (it hands you URLs, you decide what to do with them)
- Not affiliated with moviebox.ph
- Not a scraping tool — it depends on the upstream API staying reachable
- Not multi-user — bookmarks and history are per-browser, not per-account

---

## Quickstart

```bash
git clone https://github.com/faisaljs/Moviebox-API
cd Moviebox-API
pip install -r requirements.txt
python main.py
```

Server boots on `http://127.0.0.1:8000`. Three entry points:

- `http://127.0.0.1:8000/` — the app (hero carousel, catalog, player, bookmarks, history)
- `http://127.0.0.1:8000/dashboard` — operator console (provider health, diagnostics, live stream debug)
- `http://127.0.0.1:8000/docs` — Swagger UI

Dev with autoreload:

```bash
RELOAD=1 python main.py
```

Custom port:

```bash
PORT=9000 python main.py
```

Bind to all interfaces (use with a reverse proxy that adds auth):

```bash
MOVIEBOX_BIND_HOST=0.0.0.0 python main.py
```

Docker:

```bash
docker compose up -d
```

The Compose file publishes on `127.0.0.1:8000` and reads settings from `.env` if present.

Requires Python 3.10+ (union type syntax in the codebase).

---

## Endpoints

### Home & browse

| Method | Path                | Purpose                           |
| ------ | ------------------- | --------------------------------- |
| `GET`  | `/home`             | Featured sections and banners     |
| `GET`  | `/home/all`         | Flattened deduped feed            |
| `GET`  | `/sections`         | List every home section           |
| `GET`  | `/browse/{section}` | Direct access to any home section |
| `GET`  | `/movies`           | Home-fallback catalog for movies  |
| `GET`  | `/tv-series`        | Home-fallback catalog for TV      |
| `GET`  | `/animation`        | Home-fallback catalog for anime   |

### Search & metadata

| Method | Path              | Purpose                              |
| ------ | ----------------- | ------------------------------------ |
| `GET`  | `/search`         | Full-text search against upstream    |
| `GET`  | `/search/suggest` | Typeahead (`?enrich=true` for slugs) |
| `GET`  | `/detail/{slug}`  | Full metadata for a subject          |

### Stream & subtitles

| Method | Path                                        | Purpose                     |
| ------ | ------------------------------------------- | --------------------------- |
| `GET`  | `/api/stream/{subject_id}`                  | Direct video sources        |
| `GET`  | `/api/stream/{subject_id}/proxy`            | Range-aware MP4 passthrough |
| `GET`  | `/api/stream/{subject_id}/captions`         | Subtitle list               |
| `GET`  | `/api/stream/{subject_id}/subtitles/{lang}` | SRT → VTT inline            |

### Providers

| Method | Path               | Purpose                                         |
| ------ | ------------------ | ----------------------------------------------- |
| `GET`  | `/providers`       | Live provider health with circuit breaker state |
| `POST` | `/providers/probe` | Force-probe all providers now                   |
| `POST` | `/providers/reset` | Clear all circuit breakers                      |
| `GET`  | `/api/hosts`       | Backwards-compat host status                    |

### Diagnostics

| Method | Path                  | Purpose                              |
| ------ | --------------------- | ------------------------------------ |
| `GET`  | `/health`             | Liveness, cache state, provider snapshot |
| `GET`  | `/api/tabs`           | Probe tab IDs                        |
| `GET`  | `/api/tabs/variants`  | Try every known filter payload shape |
| `GET`  | `/api/debug/upstream` | Raw upstream passthrough             |
| `GET`  | `/debug/tokens`       | Show cached bearer tokens            |
| `POST` | `/debug/fetch-token`  | Force a fresh token harvest          |
| `POST` | `/debug/play`         | Direct `/subject/play` call          |

---

### `GET /home`

Returns the operating list from the moviebox home feed, grouped into sections. Banner sections and `SUBJECTS_*` rows are normalized into the same item shape.

```bash
curl http://127.0.0.1:8000/home | jq
```

```json
{
  "status": "success",
  "host": "moviebox.ph",
  "sections": [
    {
      "section": "Banner",
      "count": 13,
      "items": [
        {
          "name": "Ramayana [Hindi][CAM]",
          "poster_url": "https://.../cover.jpg",
          "slug": "ramayana-hindi-cam-qjbmxfzB2a2",
          "subject_id": "1814538579394059168",
          "badge": "Hindi"
        }
      ]
    }
  ]
}
```

### `GET /movies`, `/tv-series`, `/animation`

Home-fallback catalogs. Each returns 24 items from whichever home sections match the category keywords. `?source=filter` forces the `/subject/filter` endpoint (which currently sentinels for guests — see `/api/tabs/variants`).

### `GET /api/stream/{subject_id}`

```bash
curl "http://127.0.0.1:8000/api/stream/9035065306426868432?detail_path=the-matrix-reloaded-hindi-63q55q5HqLa&se=0&ep=0" | jq
```

Returns `has_resource`, `sources[]` (resolution, format, codec, url, size, duration), `hls[]`, `dash[]`, `free_episodes`, `limited`.

**Bidirectional fallback:** if you ask for `(se=0, ep=0)` on a series, upstream returns nothing — the route auto-retries `(1,1)` and reports `se=1, ep=1, fell_back_to_movie: false`. If you ask for `(se=5, ep=3)` on a movie, upstream returns nothing — the route auto-retries `(0,0)` and reports `se=0, ep=0, fell_back_to_movie: true`. Callers don't need to know which kind of title they're dealing with.

### `GET /api/stream/{subject_id}/proxy`

Range-aware MP4 passthrough. Drop into media servers (Jellyfin, Plex, Infuse, VLC) that can't set custom headers.

```bash
# full file
curl -O "http://127.0.0.1:8000/api/stream/9035065306426868432/proxy?detail_path=the-matrix-reloaded-hindi-63q55q5HqLa&res=1080p"

# ranged seek
curl -H "Range: bytes=0-1048575" "http://127.0.0.1:8000/api/stream/9035065306426868432/proxy?detail_path=...&res=best" -o chunk.mp4
```

Forwards `Range` upstream, returns `206` with `Content-Range` on partial. Full-file requests stream through a 64KB chunked iterator.

### `GET /api/stream/{subject_id}/subtitles/{lang}`

Fetches the SRT, strips index lines, converts timestamps, prepends `WEBVTT`. Drop-in for a `<track>` element.

```bash
curl "http://127.0.0.1:8000/api/stream/9035065306426868432/subtitles/ar?detail_path=the-matrix-reloaded-hindi-63q55q5HqLa&se=0&ep=0" | head -20
```

```vtt
WEBVTT

00:00:17.833 --> 00:00:18.916
[Vision] <i>Who am I?</i>
```

SRT formatting tags (`<i>`, `<b>`, `{\an8}`) survive the conversion.

### `GET /providers`

Live provider state:

```json
{
  "default_host": "moviebox.ph",
  "provider_count": 7,
  "healthy": 7,
  "degraded": 0,
  "providers": [
    {
      "host": "moviebox.ph",
      "alive": true,
      "circuit_open": false,
      "consecutive_failures": 0,
      "total_success": 25,
      "total_failure": 0,
      "avg_latency_ms": 374,
      "last_error": null
    }
  ],
  "circuit_breaker": { "threshold": 3, "window_seconds": 60 }
}
```

### `GET /health`

```json
{
  "status": "ok",
  "version": "2.9.1",
  "default_host": "moviebox.ph",
  "known_hosts": ["moviebox.ph", "movie-box.co", ...],
  "providers": {
    "moviebox.ph": { "alive": true, "latency_ms": 374, "fails": 0, "circuit_open": false }
  },
  "tokens_cached": 1,
  "domain_cached": "https://mzfi.me",
  "domain_expires_in": 287,
  "stream_cache_size": 3,
  "home_cache_size": 1,
  "client_pool_connections": 2
}
```

---

## Frontend at `/`

Single-file vanilla JS, no build step, no dependencies. Served by the same FastAPI process.

**Views:**

- **Home** — hero carousel (auto-rotating, arrows, dots, Ken Burns zoom on the backdrop), then continue-watching (deduped by show, position ≥ 30s, top 8), then every home section as a horizontal scroll row. Includes **Refresh** and **🎲 Surprise me** buttons.
- **Catalog** — type tabs (Movies / TV / Anime), sort dropdown (Recommended / Newest / Hot / Rating), grid/list view toggle, load-more pagination
- **Bookmarks** — everything you've hearted, sorted by save time, "Clear all" button
- **History** — every episode you've watched with progress bar, resume button, ✓ Watched badge on finished entries
- **Detail** — poster, description, metadata, cast, dubs ("Watch in"), Play button or season/episode grid, bookmark toggle, Copy link, Trailer button (when available), ← Back navigation
- **Player** — modal overlay with quality picker, subtitle picker (preference persisted), resume-from-history, keyboard shortcuts, ‹ Prev / Next › episode navigation, auto-play next on video end

**UI features:**

- Skeleton loaders on every view — content fades in when fetch resolves
- Lazy image loading with fade-in on poster tiles and hero backdrops
- IntersectionObserver-based lazy row render — sections below the fold don't render until you scroll near them
- Language filter in the header — filters home sections, catalog, and search by `[Hindi]` / `[Tamil]` / etc. tags
- Load-more button with `(fetched of total)` counter
- Grid/list view toggle (persisted per browser)
- Sort dropdown (persisted per browser)
- Scroll-to-top button (appears after 500px scroll, hides over player overlay)
- `/` keyboard shortcut focuses search box
- Episode prev/next in player, auto-play next on end
- Mark-as-watched on continue-watching cards
- Back button on detail page preserves browser history
- Copy-link button on detail page

**Persistence** (browser `localStorage`, not server):

| Key            | Contents                                          |
| -------------- | ------------------------------------------------- |
| `mb.bookmarks` | Saved titles `{ slug: { ..., saved_at } }`        |
| `mb.history`   | Watch progress `{ "slug\|sN\|eM": { ..., pos } }` |
| `mb.lang`      | Selected content language filter                  |
| `mb.subLang`   | Last-used subtitle language code                  |
| `mb.viewMode`  | Grid or list                                      |
| `mb.sort`      | Last-used sort option                             |

Bookmarks and history follow the browser, not the account. Move to a different browser and you start fresh. Clear site data and you lose them. This is the trade-off for keeping the backend stateless.

**Player keyboard shortcuts:**

| Key           | Action                         |
| ------------- | ------------------------------ |
| `Space` / `k` | Play / pause                   |
| `←` / `→`     | Seek ±5s                       |
| `↑` / `↓`     | Volume ±10%                    |
| `f`           | Fullscreen                     |
| `m`           | Mute                           |
| `Esc`         | Close player / exit fullscreen |

---

## Dashboard at `/dashboard`

Separate operator console for debugging the API itself. Same single-file approach.

**Views:**

- **Health** — auto-refreshes every 5s, live provider table, cache stats
- **Providers** — full per-host circuit breaker state, Probe All and Reset buttons
- **Home** — live `/home` feed rendered as poster rows
- **Search** — typeahead with slug preview, click any result to jump to Stream
- **Browse** — free-form section name input
- **Stream** — manual SID / slug / se / ep entry, shows source table and captions with inline player
- **Debug** — one button per diagnostic endpoint, JSON output with syntax highlighting
- **API** — static reference for every route

---

## Architecture

### Module layout

```
config.py            env vars + headers + constants
state.py             mutable globals (client, tokens, caches)
providers.py         provider health, circuit breaker, probe loop
upstream.py          token cache, bff_request (failover), player, stream resolution
helpers.py           normalize, srt_to_vtt, pick_mp4_stream
env_loader.py        .env file discovery
main.py              FastAPI app + lifespan + middleware + / and /dashboard
routes/              APIRouter handlers grouped by feature
app.html             user-facing frontend
api_dashboard.html   operator console
```

No circular imports. Import order: `config → state → providers → upstream → routes → main`. `helpers` is a leaf module.

The rule throughout: `import state` / `import providers` — never `from state import client`. Mutable references stay live via module attribute access.

### Guest tokens per provider

Each mirror issues its own guest JWT via the `x-user` response header. Tokens are cached per host. On 401 **or** 400 with `{"message": "invalid token"}`, the token is cleared, re-acquired, and the request retried once on the same host. Upstream changed from 401 to 400 for stale tokens at some point — both paths are handled.

**Token harvest uses a fresh `httpx.AsyncClient` per call** with only `User-Agent` and `Referer`. The shared client accumulates `set-cookie: token=` from the probe loop and prior `/home` calls, and once it has a stale cookie, upstream returns 200 without an `x-user` header — silent harvest failure. The fresh client guarantees a clean session.

**Browser-fingerprint headers block the harvest.** Upstream refuses to issue `x-user` for requests carrying `sec-fetch-site: cross-site` or `sec-fetch-mode: cors`. So the harvest uses minimal headers, then the resulting token is attached to normal requests with full browser headers.

### Player domain

Stream URLs live on a different host than the BFF. Fetched from `/media-player/get-domain`, cached for 300s, currently resolves to `https://mzfi.me`. **That domain is a static OSS frontend** — the `/wefeed-h5api-bff/subject/play` API stayed on `API_BASE`. The player domain is only used to build the `Referer` header, so upstream treats the request as coming from a legitimate player. The actual `/subject/play` call goes to `h5-api.aoneroom.com`.

On stream failure, the domain cache is invalidated and re-discovered once before surfacing an error.

### Provider failover

Every BFF request tries the primary first, then falls over to the next healthy provider on network failure, 5xx, 429 (honoring Retry-After), or non-JSON. Per-host circuit breaker opens after 3 consecutive failures for 60s. A background probe loop cycles one host per `PROVIDER_PROBE_INTERVAL` seconds, keeping latency and health fresh.

All 7 known mirrors share the same aoneroom backend — the failover is pure resilience, not multiple catalogs.

### SRT → VTT

`/subtitles/{lang}` fetches the SRT, strips numeric index lines, converts `,` timestamp separators to `.`, prepends `WEBVTT`, collapses whitespace. Italics and other SRT tags survive.

---

## Project layout

```
.
├── main.py
├── config.py
├── state.py
├── providers.py
├── upstream.py
├── helpers.py
├── env_loader.py
├── app.html
├── api_dashboard.html
├── routes/
│   ├── __init__.py
│   ├── providers.py
│   ├── home.py
│   ├── catalog.py
│   ├── search.py
│   ├── stream.py
│   └── diagnostics.py
├── requirements.txt
├── verify.py
├── install.sh
├── Dockerfile
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

## Verification

`verify.py` runs a live integration pass against a running server. It chains real requests — pulls a slug from `/home` or `/search`, then feeds `/detail`, `/api/stream`, `/captions`, `/proxy`, `/subtitles`. It also exercises `/providers`, `/api/hosts`, search with enrichment, tab diagnostics, debug endpoints, and both UI routes.

```bash
# server must be running
python verify.py

# or against a remote host
python verify.py https://your-host
```

53 checks. Validates byte-level MP4 signature on the proxy (`ftyp` box at offset 4), verifies WEBVTT prefix on subtitle conversion, verifies enriched suggestions return non-null slugs. Auto-picks the search fixture with the most stream sources so proxy/caption tests run against something real.

Fast-fails with exit 2 if the server is unreachable, exit 1 on any check failure, exit 0 on clean pass.

---

## Environment

Key variables (all read from env or `.env`):

| Variable                        | Default       | Notes                                             |
| ------------------------------- | ------------- | ------------------------------------------------- |
| `PORT`                          | `8000`        | Listen port                                       |
| `RELOAD`                        | `0`           | `1` enables autoreload (dev)                      |
| `REQUEST_TIMEOUT`               | `25`          | Upstream timeout, seconds                         |
| `MOVIEBOX_BIND_HOST`            | `127.0.0.1`   | Bind address; Docker sets `0.0.0.0` inside container |
| `CORS_ORIGINS`                  | empty         | Optional comma-separated trusted origins          |
| `MOVIEBOX_HOST`                 | `moviebox.ph` | Primary provider                                  |
| `MOVIEBOX_HOSTS`                | 7 mirrors     | Comma-separated                                   |
| `PROVIDER_PROBE_INTERVAL`       | `60`          | Seconds between probe ticks                       |
| `CIRCUIT_BREAKER_THRESHOLD`     | `3`           | Failures before host opens                        |
| `CIRCUIT_BREAKER_SECONDS`       | `60`          | How long host stays open                          |

The app reads `.env` from the current directory, then `$XDG_CONFIG_HOME/moviebox/.env`, then the app source directory. Set `MOVIEBOX_ENV_FILE` to choose a specific file. Exported shell variables take precedence.

---

## Deployment notes

- **Network exposure** — direct runs bind to localhost. Docker Compose publishes on `127.0.0.1`. To expose a deployment, deliberately change `MOVIEBOX_BIND_HOST` and put authentication in front of it; this app has no user authentication.
- **Debug endpoints** — `/debug/tokens`, `/debug/fetch-token`, and `/debug/play` write to the token cache and sign upstream requests. Fine on `127.0.0.1`; remove or gate them before exposing.
- **CORS** — same-origin frontend use needs no CORS setting. Set `CORS_ORIGINS` only for specific trusted web clients.
- **Behind a reverse proxy** — forward the full path. Routes assume `/` as root.
- **Healthcheck** — point your orchestrator at `/health`.
- **Rate limits** — upstream is unauthenticated for guests. Heavy polling will get throttled.
- **ToS** — you're calling a third party's private API. Behave accordingly.

---

## Troubleshooting

### `/search` returns 502 "All N providers failed"

Token harvest failed. Hit `POST /debug/fetch-token` to see what happened. Check the server log for `[fetch_token]` lines — they print the exact fail path (`no x-user header`, `no token in x-user payload`, request exception). Most common cause: `MOVIEBOX_HOSTS` is set to a dead mirror list, or a corporate firewall is blocking `h5-api.aoneroom.com`.

### `/api/stream/*` returns 502 "player HTTP 400"

Player domain is stale. Restart the server to reset `state.domain_cache`, or `POST /providers/reset` and retry. If it persists, `mzfi.me` may have moved again — check `/debug/play` output for the domain it's using.

### Stream proxy returns 502

Upstream CDN might be blocking the referer. Check `/api/stream/{sid}` first — if sources are present, the URLs are live and the proxy should work. If empty, the episode may be gated or mid-upload.

### Tokens aren't being cached (`tokens_cached: 0` in `/health`)

The shared `httpx.AsyncClient` accumulated a stale `set-cookie` from the probe loop. Fixed in the current code by using a fresh client per harvest — if you're on old code, restart fixes it. If it persists on current code, paste the `[fetch_token]` log line.

### Home feed is empty

`/home` works without auth. If it fails, upstream is down or `MOVIEBOX_HOST` is misconfigured. Try `curl -s https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph` directly.

### `/movies` and `/catalog?type=movie` show different counts

`/catalog` no longer exists. `/movies` is home-fallback only. If you're looking for a full indexed catalog, that feature was removed in 2.9.1 along with the SQLite walker. Use `/search` or `/browse/{section}` instead.

### Search misses a known title

Upstream `/subject/search` is relevance-ranked, not exhaustive. If you have the exact slug, use `/detail/{slug}` directly — that endpoint always works.

### Frontend `/` 404

`app.html` missing. Confirm the file exists next to `main.py`. `Dockerfile` copies it explicitly.

---

## License

MIT — see [LICENSE](LICENSE) for the full text.

---

## Author

**Faisal** ([@faisaljs](https://github.com/faisaljs))

- GitHub: [github.com/faisaljs](https://github.com/faisaljs)
- Repo: [github.com/faisaljs/Moviebox-API](https://github.com/faisaljs/Moviebox-API)
- Issues / PRs: [github.com/faisaljs/Moviebox-API/issues](https://github.com/faisaljs/Moviebox-API/issues)

Not affiliated with moviebox.ph. Provided as-is. You are responsible for how you use it.