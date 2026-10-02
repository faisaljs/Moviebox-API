# MovieBox API Pro

A pure REST API wrapper around [moviebox.ph](https://moviebox.ph).

No scraping. No HTML parsing. No headless browser. It talks the exact same private JSON API the moviebox web player talks — `h5-api.aoneroom.com/wefeed-h5api-bff` — and re-exposes it as a clean, self-hosted REST surface.

Built for people who want to wire moviebox into their own apps, scripts, bots, dashboards, or media servers without reverse-engineering the network tab every time the site ships an update.

---

## What it does

- **Discovery** — banners, featured blocks, and category rows from the moviebox home feed
- **Catalog** — paginated movies, TV series, and animation
- **Search** — full search + autocomplete suggestions
- **Metadata** — full detail tree for any subject (episodes, seasons, languages, artwork)
- **Streams** — direct MP4 sources per resolution, plus HLS and DASH manifests
- **Subtitles** — full caption list per episode / movie

## What it isn't

- Not a proxy that streams video through your server (yet — see *Extensions*)
- Not a downloader (it hands you URLs, you decide what to do with them)
- Not affiliated with moviebox.ph
- Not a scraping tool — it depends on the upstream API staying reachable

---

## Quickstart

```bash
git clone https://github.com/faisaljs/Moviebox-API
cd Moviebox-API
pip install -r requirements.txt
python main.py
```

Server boots on `http://localhost:8000`. Open it in a browser and you get the dashboard, which lists every endpoint with a one-click test button.

For dev with autoreload:

```bash
RELOAD=1 python main.py
```

For a specific port:

```bash
PORT=9000 python main.py
```

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | HTML dashboard |
| `GET` | `/health` | Service + cache state |
| `GET` | `/home` | Featured sections and banners |
| `GET` | `/movies` | Movie catalog (paginated) |
| `GET` | `/tv-series` | TV catalog (paginated) |
| `GET` | `/animation` | Animation catalog (paginated) |
| `GET` | `/search` | Full-text search |
| `GET` | `/search/suggest` | Autocomplete |
| `GET` | `/detail/{slug}` | Full metadata for a subject |
| `GET` | `/api/stream/{subject_id}` | Direct video sources |
| `GET` | `/api/stream/{subject_id}/captions` | Subtitle list |

### `GET /home`

Returns the operating list from the moviebox home feed, grouped into sections. Banner sections and `SUBJECTS_*` rows are both normalized into the same item shape.

**Example**

```bash
curl http://localhost:8000/home | jq
```

**Response**

```json
{
  "status": "success",
  "sections": [
    {
      "section": "Banner",
      "count": 5,
      "items": [
        {
          "name": "Attack on Titan",
          "poster_url": "https://.../cover.jpg",
          "slug": "attack-on-titan-hindi-kGWQOIx0d4",
          "subject_id": "56988683026712168",
          "badge": "TOP"
        }
      ]
    },
    {
      "section": "Trending Now",
      "count": 20,
      "items": [
        {
          "name": "Breaking Bad",
          "poster_url": "https://.../bb.jpg",
          "slug": "breaking-bad-ej6Bp0MCAo7",
          "subject_id": "6207982430134357800",
          "badge": null,
          "rating": "9.5"
        }
      ]
    }
  ]
}
```

The item shape is consistent across banner rows and subject rows, so you can flatten everything into a single feed without branching on section type.

---

### `GET /movies`, `GET /tv-series`, `GET /animation`

Paginated catalogs. Each maps to a fixed `tabId` on the upstream filter endpoint.

**Query parameters**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | `1` | 1-indexed |
| `sort` | string | `RECOMMEND` | Upstream-honored values: `RECOMMEND`, `NEWEST`, `RATING`, etc. |

**Example**

```bash
curl "http://localhost:8000/movies?page=2&sort=NEWEST" | jq
```

**Response**

```json
{
  "page": 2,
  "per_page": 24,
  "total": 15840,
  "items": [
    {
      "name": "Dune: Part Two",
      "poster_url": "https://.../dune2.jpg",
      "slug": "dune-part-two-xxxxxxxx",
      "subject_id": "1234567890123456789",
      "badge": "NEW",
      "rating": "8.7",
      "year": "2024"
    }
  ]
}
```

---

### `GET /search`

**Query parameters**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `q` | string | yes | Min length 1 |
| `page` | int | no | Default `1` |

```bash
curl "http://localhost:8000/search?q=matrix" | jq
```

Returns `{ query, page, total, items[] }` with the same item shape as the catalogs.

---

### `GET /search/suggest`

Autocomplete. Lighter payload, optimized for type-ahead.

```bash
curl "http://localhost:8000/search/suggest?q=break" | jq
```

```json
{
  "suggestions": [
    {
      "title": "Breaking Bad",
      "slug": "breaking-bad-ej6Bp0MCAo7",
      "subject_id": "6207982430134357800"
    }
  ]
}
```

---

### `GET /detail/{slug}`

Raw passthrough of the upstream detail endpoint. The response is the full tree — subject info, seasons, episodes, available languages, artwork variants.

```bash
curl "http://localhost:8000/detail/breaking-bad-ej6Bp0MCAo7" | jq
```

The `slug` comes from `/home`, `/search`, or any catalog endpoint (`slug` field).

---

### `GET /api/stream/{subject_id}`

Resolves direct playable sources for a subject (or a specific episode).

**Path parameter**

- `subject_id` — the `subject_id` from any discovery/search endpoint

**Query parameters**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `detail_path` | string | required | The `slug` |
| `se` | int | `1` | Season number |
| `ep` | int | `1` | Episode number |

**Example**

```bash
curl "http://localhost:8000/api/stream/6207982430134357800?detail_path=breaking-bad-ej6Bp0MCAo7&se=1&ep=1" | jq
```

**Response**

```json
{
  "subject_id": "6207982430134357800",
  "se": 1,
  "ep": 1,
  "has_resource": true,
  "sources": [
    {
      "resolution": "1080p",
      "format": "MP4",
      "url": "https://.../1080p.mp4",
      "size": 1234567890,
      "duration": 2880,
      "codec": "H264"
    },
    {
      "resolution": "720p",
      "format": "MP4",
      "url": "https://.../720p.mp4",
      "size": 812345678,
      "duration": 2880,
      "codec": "H264"
    }
  ],
  "hls": [],
  "dash": [],
  "free_episodes": 3,
  "limited": false,
  "note": null
}
```

- `sources[]` — direct MP4 links per resolution
- `hls[]` / `dash[]` — manifest URLs when the subject uses adaptive streaming
- `free_episodes` — how many episodes are watchable without an account upstream
- `limited` — upstream flags some subjects as region- or tier-restricted

If `has_resource` is `false`, the `note` field explains why (usually the episode doesn't exist or is paid-gated).

---

### `GET /api/stream/{subject_id}/captions`

Fetches the caption track list for the same stream that `/api/stream` resolved.

Same query parameters as `/api/stream/{subject_id}`.

```bash
curl "http://localhost:8000/api/stream/6207982430134357800/captions?detail_path=breaking-bad-ej6Bp0MCAo7&se=1&ep=1" | jq
```

```json
{
  "subject_id": "6207982430134357800",
  "se": 1,
  "ep": 1,
  "count": 12,
  "captions": [
    {
      "lan": "en",
      "lanName": "English",
      "url": "https://.../en.srt",
      "format": "SRT"
    }
  ]
}
```

---

### `GET /health`

Liveness + cache diagnostics. Useful as a container healthcheck.

```json
{
  "status": "ok",
  "token_cached": true,
  "domain_cached": "https://netfilm.world",
  "domain_expires_in": 287
}
```

---

## Architecture

### Guest token

moviebox's BFF issues a guest JWT on the very first unauthenticated request. It arrives in an `x-user` response header, not in the body. Every subsequent request must carry it as `Authorization: Bearer <token>`.

`main.py` handles this transparently:

1. First upstream call → response has `x-user` → parse out `token` → cache in module global
2. Every subsequent response that carries `x-user` → refresh the cached token
3. If the header is missing, fall back to parsing `set-cookie` for a `token=` value

You never see it. You never touch it.

### Player domain

Stream URLs live on a different host than the BFF. The host is fetched from `/media-player/get-domain` and can rotate. `main.py` caches it for **300 seconds** and re-fetches on expiry.

### Player headers

The stream and caption endpoints require different headers than the BFF:

- `Referer` — must be the actual play-page URL the browser would send
- `Origin` / `sec-fetch-site` — same-origin, not cross-site
- The referer includes `id`, `type`, `detailSe`, `detailEp`, and `lang` query params

`_build_player_referer()` constructs it. Change the shape there if upstream tightens the check.

### Defensive navigation

Upstream sends `null` where you'd expect an object (`{ "cover": null }`). Every nested access uses `(x or {}).get("y")` so a null in one field doesn't 502 the whole response.

---

## Project layout

```
.
├── main.py            # the whole app — routes, helpers, HTML dashboard
├── requirements.txt   # fastapi, uvicorn, httpx
├── verify.py          # live integration test — chains real requests
├── README.md
├── .env.example
└── .gitignore
```

No package structure, no ORM, no config layer. One file for the app because the app is one file's worth of logic.

---

## Verification

`verify.py` runs a live integration pass. It chains requests — pulls a real slug and subject_id from `/home`, feeds them into `/detail`, `/api/stream`, and `/api/stream/.../captions`. Every route prints `PASS` or `FAIL` with a sample.

```bash
# server must be running
python verify.py

# or against a remote host
python verify.py https://your-host
```

Exits non-zero on any failure, so it drops straight into CI or a pre-commit hook.

---

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `PORT` | `8000` | Listen port |
| `RELOAD` | `0` | `1` enables uvicorn autoreload (dev only) |

No config file. No `.env` required — the `.env.example` is a convenience.

---

## Deployment notes

- **Behind a reverse proxy** — set the proxy to forward the full path. No subpath rewriting; routes assume `/` as root.
- **Healthcheck** — point your orchestrator at `/health`.
- **Long-running** — the token is process-global. If you run multiple workers, each one acquires its own token on first request. That's fine.
- **Rate limits** — upstream is unauthenticated for guests. Heavy polling of `/home` or catalogs will get you throttled from the BFF's side. Cache your own reads if you're scraping anything on a schedule.
- **ToS** — you're calling a third party's private API. Behave accordingly.

---

## Extensions

Not implemented, but the shape of the code makes them easy:

- **Stream proxy** — a `/proxy/stream/{subject_id}` endpoint that fetches the MP4 with the right headers and pipes it through. Useful for media servers that can't set custom headers.
- **Subtitle conversion** — SRT → VTT on the fly for browser `<track>` elements.
- **Aggregate home feed** — flatten all sections from `/home` into a single deduplicated list.
- **Search across catalogs** — client-side merge of `/search` results with local filtering by year, rating, genre.
- **Redis-backed cache** — replace the module globals with a shared cache if you run multi-instance.

---

Not affiliated with moviebox.ph. Provided as-is. You are responsible for how you use it.