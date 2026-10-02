# Contributing

Short version: fork, branch, make it work, run `verify.py`, open a PR. Keep it small. Explain *why* in the PR body, not *what* — the diff shows what.

## Setup

```bash
git clone https://github.com/faisaljs/Moviebox-API
cd Moviebox-API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Server comes up on `http://localhost:8000`. Dashboard is at `/`.

```bash
# autoreload for dev
RELOAD=1 python main.py
```

## Before you open a PR

1. **Run the verifier.** With the server live:
   ```bash
   python verify.py
   ```
   Every route must print `[PASS]`. If one fails, either your change broke it or upstream drifted — figure out which before opening the PR.

2. **Touch the smallest surface possible.** One concern per PR. Don't bundle a refactor with a feature.

3. **No new dependencies** unless there's a real reason. This project is fastapi + httpx + uvicorn. Adding an SDK, an ORM, a config framework, a logging lib — those need justification in the PR body. Nine times out of ten the stdlib covers it.

4. **Don't reformat untouched code.** Diffs should be reviewable in under a minute.

## What lands

- Bug fixes against upstream API changes
- New endpoints that map to real BFF routes (find them in the web player's network tab)
- Response shape improvements — cleaner field names, more complete data extraction
- Caching, connection pooling, retry logic that measurably reduces upstream calls
- Better error messages when upstream returns something weird
- Docker / deployment improvements

## What doesn't

- Auth-bypass tricks, scraping fallbacks, "when the API fails, load the HTML instead" — the whole point is pure API
- Anything that adds an external service dependency
- Rewrites of the module structure without a concrete problem being solved
- Tests that hit live upstream in CI (see below)

## Debugging upstream changes

The BFF is undocumented and can shift without warning. When a route breaks:

1. Open `moviebox.ph` in a browser, DevTools → Network → filter `wefeed-h5api-bff`
2. Click around until you see the request your endpoint is wrapping
3. Compare headers, params, and payload shape to what `main.py` sends
4. Update `DEFAULT_HEADERS` / `PLAYER_HEADERS` / payload keys to match

The token flow (`x-user` header → cached bearer) and the player-domain flow (`/media-player/get-domain` → cached) are the two places upstream changes will hit first. Check those before digging into a specific route.

## Code style

- Type hints on function signatures
- `(x or {}).get("y")` for defensive navigation — the BFF sends `null` where you'd expect an object
- Comments only where the reasoning isn't obvious from the code. "Send the request" is noise. "Upstream refreshes the JWT on every response that carries an x-user header" is signal.
- Async everywhere. No blocking `httpx.get` in a route.
- Route handlers stay thin. Shared logic goes into `_helper` functions.

## Testing

There's no unit test suite. The API surface is a thin proxy — unit tests would just re-assert dict shapes and rot the moment upstream shifts. `verify.py` is the integration test.

If you want to add automated tests, they need to be:
- Against a recorded upstream fixture (VCR-style), not live
- Run in CI without network access
- Small — cover the parsing logic in `_get_category_data`, `/home` section extraction, and caption ID selection, not the whole request path

## Commit messages

Plain English, present tense, one line. Body if the change isn't self-evident.

```
fix: handle null cover on /home banner items
add: /health endpoint for token + domain cache state
refactor: extract player referer builder
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

That's usually enough to diff and fix in one pass.