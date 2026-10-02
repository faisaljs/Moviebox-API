# MovieBox API Pro

Pure REST wrapper around `moviebox.ph`'s BFF (`h5-api.aoneroom.com/wefeed-h5api-bff`).
Zero scraping — talks the same JSON the web player talks, with auto-acquired guest JWT.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | HTML dashboard |
| GET | `/home` | Featured sections + banners |
| GET | `/movies?page=N&sort=S` | Movie catalog |
| GET | `/tv-series?page=N&sort=S` | TV catalog |
| GET | `/animation?page=N&sort=S` | Animation catalog |
| GET | `/search?q=…&page=N` | Full search |
| GET | `/search/suggest?q=…` | Autocomplete |
| GET | `/detail/{slug}` | Full metadata tree |
| GET | `/api/stream/{subject_id}?detail_path=…&se=1&ep=1` | Direct MP4/HLS/DASH sources |
| GET | `/api/stream/{subject_id}/captions?detail_path=…&se=1&ep=1` | Subtitle list |
| GET | `/health` | Token cache + domain TTL |

## Run

```bash
pip install -r requirements.txt
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000