# Screenshots

The repo does not ship with screenshots. This file is a text tour of what the
app looks like, plus instructions for capturing images if you want to add them.

Every view described here is reachable from a fresh `python main.py` with no
setup beyond `pip install -r requirements.txt`.

---

## Home (`/`)

The landing page. Hero carousel at the top — auto-rotates every 6 seconds with
a slow Ken Burns zoom on the backdrop, arrows and dots appear on hover.

Below the hero:

- A `Continue Watching` row (only when you have in-progress episodes; deduped by show, capped at 8)
- Every home section as a horizontal scroll row — `Trending Now`, `🔥Cinema`, `Bollywood`, `Top Anime`, etc.
- Each section header has a `See all →` link to `#/catalog?section={name}`

Top of the page: `↻ Refresh` and `🎲 Surprise me` buttons. Refresh re-fetches
`/home`. Surprise me picks a random title from `/home/all`, filters by your
selected language, and jumps to its detail page.

Skeleton loaders show while `/home` is fetching. Rows below the fold don't
render until you scroll near them (IntersectionObserver, 200px margin). Poster
images lazy-load with a fade-in.

---

## Search (header, any view)

The search input sits in the sticky header. Press `/` from anywhere to focus it.

Typeahead fires after 300ms of typing, hits `/search/suggest?enrich=true`, and
shows a dropdown with matched titles. Each result is a link to its detail page
(slugs are resolved via a second `/search` call per suggestion server-side).

Press Enter to skip the dropdown and go straight to the full search results
page at `#/catalog?q=...`.

---

## Catalog (`#/catalog`)

Full-width grid of poster cards. Toolbar at the top has:

- Type tabs: `Movies` / `TV` / `Anime`
- Sort dropdown (only on non-search, non-section views): `Recommended` / `Newest` / `Hot` / `Rating`
- Grid/list view toggle (`⊞` / `☰`)

Results load 24 at a time. A `Load more (24 of 342)` button at the bottom
appends the next page without losing scroll position. When exhausted it shows
`End of results (342 of 342)`.

List view renders each card as a horizontal row — small 80px poster on the left,
title and metadata on the right, resume button underneath.

Sort and view mode persist in `localStorage` (`mb.sort`, `mb.viewMode`).

---

## Detail (`#/detail/{slug}`)

Full metadata page. Layout:

- Left column: large poster with rounded corners and a drop shadow
- Right column:
  - Title
  - Metadata chips (year, IMDb rating, genre, country)
  - Description
  - Action buttons: `♡ Bookmark` / `♥ Saved`, `🔗 Copy link`, `▶ Trailer` (when available)
  - `Watch in` chips if multiple dubs exist — click to switch language version
  - `▶ Play` button (movies) or season/episode grid (series)
  - Cast chips

A `← Back` button sits above the header, above the fold.

For series: episodes render as buttons grouped by season. Clicking one opens
the player at that episode.

---

## Player (modal overlay)

Full-screen dark overlay. HTML5 `<video>` streaming through
`/api/stream/{sid}/proxy` with Range support — seeking works out of the box.

Controls in the bar below the video:

- `‹ Prev` / `Next ›` episode buttons (only for series with multiple episodes)
- Quality picker (`360p`, `480p`, `720p`, `1080p` — whatever upstream provides)
- Subtitle picker — defaults to your last-used language, falls back to English

On open:

- If you've watched before, a toast says `Resumed from M:SS` and playback starts there
- If the episode has no streams but a fallback exists (movie/series mismatch), the route silently falls back — the input fields update to show what's actually playing

Auto-play next episode: when the video ends and there's a next episode, a
`Next episode starting…` toast fires and the next one opens after 1.5s.

Keyboard shortcuts: `Space` / `k` play/pause, `←` `→` seek ±5s, `↑` `↓` volume,
`f` fullscreen, `m` mute, `Esc` close.

---

## Bookmarks (`#/bookmarks`)

Every card you've hearted, sorted by save time, newest first. Clear-all button
in the section header. Empty state is a centered `♡` with "No bookmarks yet —
click the heart on any poster to save it here."

Bookmarks live in `localStorage` under `mb.bookmarks`. They do not sync across
browsers or devices. Moving to a different browser profile starts fresh.

---

## History (`#/history`)

Every episode you've watched, sorted by `updated_at` descending. Each card shows:

- Poster + title
- Progress bar (position / duration)
- `▶ Resume M:SS` button
- Season/episode badge if it's a series
- Green `✓ Watched` badge on finished entries

Watch history lives in `localStorage` under `mb.history`. Same non-sync caveat
as bookmarks.

---

## Dashboard (`/dashboard`)

Separate operator console, different look — dark sidebar, JSON viewer, monospace
where it matters.

Views in the sidebar:

- **Health** — auto-refreshes every 5s, live provider table, cache stats
- **Providers** — full per-host circuit breaker state, Probe All and Reset
- **Home** — live `/home` feed as poster rows
- **Search** — typeahead with slug preview, click any result to jump to Stream
- **Browse** — free-form section name input
- **Stream** — manual SID / slug / se / ep entry, source table, inline player
- **Debug** — one button per diagnostic endpoint, JSON output with syntax highlighting
- **API** — static reference for every route

---

## Capturing screenshots

If you want to add screenshots to the repo:

1. Start the server:

   ```bash
   python main.py
   ```

2. Open the app in a browser at `http://127.0.0.1:8000/`
3. Set viewport to **1440×900**, browser zoom **100%**
4. Hide browser chrome — use devtools "Take a screenshot" (Firefox) or the
   command palette "Capture screenshot" (Chrome), or the headless command below
5. Save with the names listed in the next section

Suggested file names (so `Screenshots.md` and `README.md` stay in sync if you
reference them):

| Filename               | View                                      |
| ---------------------- | ----------------------------------------- |
| `home.png`             | `/` — home with hero carousel             |
| `catalog.png`          | `#/catalog` — grid view                   |
| `catalog-list.png`     | `#/catalog` — list view                   |
| `detail.png`           | `#/detail/{slug}` — a series with episodes |
| `player.png`           | Player overlay open                       |
| `bookmarks.png`        | `#/bookmarks` with several saved titles   |
| `history.png`          | `#/history` with in-progress entries      |
| `dashboard.png`        | `/dashboard` — health view                |

Drop them into a `screenshots/` directory at the repo root. Then add a
`## Screenshots` section to `README.md` with `<img>` tags pointing at
`screenshots/home.png`, etc.

### Headless capture

Firefox:

```bash
firefox --screenshot=screenshots/home.png --window-size=1440,900 http://127.0.0.1:8000/
```

Chromium:

```bash
chromium --headless --disable-gpu \
  --screenshot=screenshots/home.png \
  --window-size=1440,900 \
  http://127.0.0.1:8000/
```

Note: headless captures can't interact with the page — the hero carousel will
show slide 0, the player won't be open, etc. For anything interactive, use
devtools screenshot mode in a real browser.