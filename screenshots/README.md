# Screenshots

Frames captured from a running instance of MovieBox API Pro. All images at
1440×900, browser zoom 100%, captured Nov 8 2026.

---

## Home

The landing page. Hero carousel at top, continue-watching row below (when
present), then every home section as a horizontal scroll row.

![Home](home.png)

---

## Search

Header typeahead — hits `/search/suggest?enrich=true` after 300ms of typing,
shows matched titles as clickable links.

![Search](search.png)

---

## Catalog

Grid view of the catalog. Type tabs, sort dropdown, grid/list toggle in the
toolbar.

![Catalog](catalog.png)

### Filtered to movies

![Catalog — movies](ctg-movie.png)

### Filtered to TV series

![Catalog — TV](ctg-tv.png)

### Filtered to anime

![Catalog — anime](ctg-anime.png)

---

## Detail / Episodes

Series detail page with season/episode grid. Poster, metadata, cast, dubs, and
play button (or episode list for series).

![Episode detail](episode.png)

---

## Player

Modal overlay. HTML5 video through `/api/stream/{sid}/proxy` with Range
support. Quality picker, subtitle picker, prev/next episode buttons, resume
position, keyboard shortcuts.

![Player](player.png)

---

## Bookmarks

Every card you've hearted, sorted by save time. Stored in the browser
(`localStorage` under `mb.bookmarks`), not on the server.

![Bookmarks](bookmark.png)

---

## Watch History

Every episode you've watched with progress bar, resume button, and
season/episode badge. Stored in the browser (`localStorage` under `mb.history`).

![Watch history](history.png)