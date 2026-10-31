"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import re
import time
import sqlite3
import hashlib
import json
from config import (
    CATALOG_DB, DEFAULT_HOST,
)
import state


_FTS_TERM_RE = re.compile(r"\w+", re.UNICODE)


def init_schema():
    conn = state.write_conn
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id TEXT PRIMARY KEY,
            title TEXT,
            poster_url TEXT,
            slug TEXT,
            rating TEXT,
            year TEXT,
            badge TEXT,
            is_movie INTEGER DEFAULT 0,
            is_tv INTEGER DEFAULT 0,
            is_anime INTEGER DEFAULT 0,
            subject_type INTEGER,
            genre TEXT,
            source_host TEXT DEFAULT 'moviebox.ph',
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_stats (
            keyword TEXT PRIMARY KEY,
            pages_walked INTEGER DEFAULT 0,
            items_seen INTEGER DEFAULT 0,
            hit_cap INTEGER DEFAULT 0,
            total_per_upstream INTEGER,
            last_walked REAL
        )
    """)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(subjects)").fetchall()}
    if "subject_type" not in cols:
        conn.execute("ALTER TABLE subjects ADD COLUMN subject_type INTEGER")
    if "genre" not in cols:
        conn.execute("ALTER TABLE subjects ADD COLUMN genre TEXT")
    if "source_host" not in cols:
        conn.execute("ALTER TABLE subjects ADD COLUMN source_host TEXT DEFAULT 'moviebox.ph'")
        conn.execute("UPDATE subjects SET source_host = 'moviebox.ph' WHERE source_host IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_title ON subjects(title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rating ON subjects(rating)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_last_seen ON subjects(last_seen)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_movie ON subjects(is_movie)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tv ON subjects(is_tv)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_anime ON subjects(is_anime)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stype ON subjects(subject_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_host ON subjects(source_host)")

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS subjects_fts USING fts5(
                title,
                content='subjects',
                content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS subjects_fts_ai AFTER INSERT ON subjects BEGIN
                INSERT INTO subjects_fts(rowid, title) VALUES (new.rowid, new.title);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS subjects_fts_ad AFTER DELETE ON subjects BEGIN
                INSERT INTO subjects_fts(subjects_fts, rowid, title) VALUES('delete', old.rowid, old.title);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS subjects_fts_au AFTER UPDATE ON subjects BEGIN
                INSERT INTO subjects_fts(subjects_fts, rowid, title) VALUES('delete', old.rowid, old.title);
                INSERT INTO subjects_fts(rowid, title) VALUES (new.rowid, new.title);
            END
        """)
        # COUNT(*) on external-content FTS reads the content table, so it
        # cannot reveal a missing or stale search index.
        try:
            conn.execute(
                "INSERT INTO subjects_fts(subjects_fts, rank) VALUES('integrity-check', 1)"
            )
        except sqlite3.DatabaseError:
            conn.execute("INSERT INTO subjects_fts(subjects_fts) VALUES('rebuild')")
    except Exception as e:
        print(f"FTS5 setup failed (search will fall back to LIKE): {e}")

    _init_user_tables(conn)

    conn.commit()


def _init_user_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_bookmarks (
            slug TEXT PRIMARY KEY,
            name TEXT,
            poster_url TEXT,
            rating TEXT,
            year TEXT,
            badge TEXT,
            saved_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_history (
            slug TEXT NOT NULL,
            se INTEGER NOT NULL,
            ep INTEGER NOT NULL,
            name TEXT,
            poster_url TEXT,
            position INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 0,
            updated_at REAL NOT NULL,
            PRIMARY KEY (slug, se, ep)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_updated ON user_history(updated_at DESC)")


def read(sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(CATALOG_DB)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def read_scalar(sql: str, params: tuple = ()):
    conn = sqlite3.connect(CATALOG_DB)
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def classify_section(title: str) -> tuple[int, int, int]:
    clean = title.lower().replace("🔥", "").replace("🆓", "").strip()
    is_movie = 1 if any(kw in clean for kw in (
        "movie", "cinema", "nollywood", "bollywood", "hollywood",
    )) else 0
    is_tv = 1 if any(kw in clean for kw in (
        "series", "tv", "show", "drama",
    )) else 0
    is_anime = 1 if any(kw in clean for kw in (
        "anime", "animation",
    )) else 0
    return (is_movie, is_tv, is_anime)


def fts_search(q: str) -> list[str] | None:
    terms = [t for t in _FTS_TERM_RE.findall(q.lower()) if len(t) >= 2]
    if not terms:
        return None
    fts_q = " ".join(f'"{t}"*' for t in terms)
    try:
        rows = read(
            "SELECT s.subject_id FROM subjects_fts fts "
            "JOIN subjects s ON s.rowid = fts.rowid "
            "WHERE subjects_fts MATCH ? ORDER BY rank LIMIT 5000",
            (fts_q,),
        )
        return [r[0] for r in rows]
    except Exception as e:
        print(f"FTS search failed: {e}")
        return None


def upsert_subject(sub: dict, section: str | None = None, source_host: str = DEFAULT_HOST) -> bool:
    if state.write_conn is None:
        return False
    sid = str(sub.get("subjectId") or "")
    if not sid:
        return False
    now = time.time()
    is_movie = is_tv = is_anime = 0
    if section:
        is_movie, is_tv, is_anime = classify_section(section)
    try:
        state.write_conn.execute("""
            INSERT INTO subjects
                (subject_id, title, poster_url, slug, rating, year, badge,
                 is_movie, is_tv, is_anime, source_host, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_id) DO UPDATE SET
                title      = COALESCE(excluded.title, subjects.title),
                poster_url = COALESCE(excluded.poster_url, subjects.poster_url),
                slug       = COALESCE(excluded.slug, subjects.slug),
                rating     = COALESCE(excluded.rating, subjects.rating),
                year       = COALESCE(excluded.year, subjects.year),
                badge      = COALESCE(excluded.badge, subjects.badge),
                is_movie   = MAX(subjects.is_movie, excluded.is_movie),
                is_tv      = MAX(subjects.is_tv, excluded.is_tv),
                is_anime   = MAX(subjects.is_anime, excluded.is_anime),
                last_seen  = excluded.last_seen
        """, (
            sid,
            sub.get("title"),
            (sub.get("cover") or {}).get("url"),
            sub.get("detailPath"),
            sub.get("imdbRatingValue"),
            (sub.get("releaseDate") or "")[:4] or None,
            sub.get("corner"),
            is_movie, is_tv, is_anime,
            source_host,
            now, now,
        ))
        return True
    except Exception as e:
        print(f"upsert {sid} failed: {e}")
        return False


def hash_operating_list(ops: list) -> str:
    sig = [(op.get("type"), op.get("title")) for op in ops]
    return hashlib.sha1(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:16]


# ─── USER DATA (bookmarks + history) ─────────────────────────────────────────

def get_bookmarks() -> list[dict]:
    rows = read("""
        SELECT slug, name, poster_url, rating, year, badge, saved_at
        FROM user_bookmarks ORDER BY saved_at DESC
    """)
    return [dict(r) for r in rows]


def upsert_bookmark(item: dict) -> bool:
    if state.write_conn is None or not item.get("slug"):
        return False
    try:
        state.write_conn.execute("""
            INSERT INTO user_bookmarks (slug, name, poster_url, rating, year, badge, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name       = COALESCE(excluded.name, user_bookmarks.name),
                poster_url = COALESCE(excluded.poster_url, user_bookmarks.poster_url),
                rating     = COALESCE(excluded.rating, user_bookmarks.rating),
                year       = COALESCE(excluded.year, user_bookmarks.year),
                badge      = COALESCE(excluded.badge, user_bookmarks.badge)
        """, (
            item["slug"], item.get("name"), item.get("poster_url"),
            item.get("rating"), item.get("year"), item.get("badge"),
            time.time(),
        ))
        return True
    except Exception as e:
        print(f"upsert_bookmark {item.get('slug')} failed: {e}")
        return False


def delete_bookmark(slug: str) -> bool:
    if state.write_conn is None:
        return False
    cur = state.write_conn.execute("DELETE FROM user_bookmarks WHERE slug=?", (slug,))
    return cur.rowcount > 0


def clear_bookmarks() -> int:
    if state.write_conn is None:
        return 0
    cur = state.write_conn.execute("DELETE FROM user_bookmarks")
    return cur.rowcount


def get_history() -> list[dict]:
    rows = read("""
        SELECT slug, se, ep, name, poster_url, position, duration, updated_at
        FROM user_history ORDER BY updated_at DESC
    """)
    return [dict(r) for r in rows]


def upsert_history(entry: dict) -> bool:
    if state.write_conn is None:
        return False
    if not entry.get("slug") or entry.get("se") is None or entry.get("ep") is None:
        return False
    try:
        state.write_conn.execute("""
            INSERT INTO user_history (slug, se, ep, name, poster_url, position, duration, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug, se, ep) DO UPDATE SET
                name       = COALESCE(excluded.name, user_history.name),
                poster_url = COALESCE(excluded.poster_url, user_history.poster_url),
                position   = excluded.position,
                duration   = excluded.duration,
                updated_at = excluded.updated_at
        """, (
            entry["slug"], int(entry["se"]), int(entry["ep"]),
            entry.get("name"), entry.get("poster_url"),
            int(entry.get("position") or 0), int(entry.get("duration") or 0),
            time.time(),
        ))
        return True
    except Exception as e:
        print(f"upsert_history {entry.get('slug')} failed: {e}")
        return False


def delete_history(slug: str, se: int | None = None, ep: int | None = None) -> int:
    if state.write_conn is None:
        return 0
    if se is not None and ep is not None:
        cur = state.write_conn.execute(
            "DELETE FROM user_history WHERE slug=? AND se=? AND ep=?",
            (slug, int(se), int(ep)),
        )
    else:
        cur = state.write_conn.execute("DELETE FROM user_history WHERE slug=?", (slug,))
    return cur.rowcount


def clear_history() -> int:
    if state.write_conn is None:
        return 0
    cur = state.write_conn.execute("DELETE FROM user_history")
    return cur.rowcount


# ─── RECOMMENDATIONS ─────────────────────────────────────────────────────────

def _rec_item(r) -> dict:
    """Convert a subjects row to the item shape the frontend renders."""
    return {
        "name": r["title"],
        "poster_url": r["poster_url"],
        "slug": r["slug"],
        "subject_id": r["subject_id"],
        "rating": r["rating"],
        "year": r["year"],
        "badge": r["badge"],
        "genre": r["genre"],
        "types": [
            t for t, f in (("movie", r["is_movie"]), ("tv", r["is_tv"]), ("anime", r["is_anime"])) if f
        ],
    }


def _watched_slugs(limit: int = 200) -> set[str]:
    rows = read("""
        SELECT DISTINCT slug FROM user_history
        ORDER BY updated_at DESC LIMIT ?
    """, (limit,))
    return {r["slug"] for r in rows}


def _rating_boost(raw) -> float:
    try:
        r = float(raw or 0)
    except (ValueError, TypeError):
        return 0.0
    if r >= 8.5: return 3.0
    if r >= 7.5: return 1.5
    if r >= 7.0: return 0.5
    return 0.0


def recommend(limit: int = 20) -> list[dict]:
    """Score-based recommendations from genre overlap + rating weight.
    Uses is_movie/is_tv flags (set at home-ingest) rather than subject_type
    (set only by enrichment) so recommendations work before enrichment runs.
    Falls back to top-rated unwatched when there's no usable genre history."""
    watched = _watched_slugs(200)

    genre_counts: dict[str, int] = {}
    if watched:
        placeholders = ",".join("?" * len(watched))
        watched_rows = read(
            f"""SELECT genre FROM subjects
                WHERE slug IN ({placeholders})
                  AND genre IS NOT NULL AND genre != ''""",
            tuple(watched),
        )
        for r in watched_rows:
            for g in (r["genre"] or "").split(","):
                g = g.strip().lower()
                if g:
                    genre_counts[g] = genre_counts.get(g, 0) + 1

    if not genre_counts:
        # Cold-start / no genre data — top rated unwatched
        if watched:
            placeholders = ",".join("?" * len(watched))
            rows = read(f"""
                SELECT subject_id, title, poster_url, slug, rating, year, badge,
                       is_movie, is_tv, is_anime, subject_type, genre
                FROM subjects
                WHERE (is_movie = 1 OR is_tv = 1)
                  AND CAST(rating AS REAL) >= 7
                  AND slug NOT IN ({placeholders})
                ORDER BY CAST(rating AS REAL) DESC
                LIMIT ?
            """, tuple(watched) + (limit,))
        else:
            rows = read("""
                SELECT subject_id, title, poster_url, slug, rating, year, badge,
                       is_movie, is_tv, is_anime, subject_type, genre
                FROM subjects
                WHERE (is_movie = 1 OR is_tv = 1)
                  AND CAST(rating AS REAL) >= 7
                ORDER BY CAST(rating AS REAL) DESC
                LIMIT ?
            """, (limit,))
        return [_rec_item(r) for r in rows]

    top_genres = {g for g, _ in sorted(genre_counts.items(), key=lambda x: -x[1])[:10]}

    if watched:
        placeholders = ",".join("?" * len(watched))
        candidates = read(f"""
            SELECT subject_id, title, poster_url, slug, rating, year, badge,
                   is_movie, is_tv, is_anime, subject_type, genre
            FROM subjects
            WHERE (is_movie = 1 OR is_tv = 1)
              AND CAST(rating AS REAL) >= 6
              AND genre IS NOT NULL
              AND genre != ''
              AND slug NOT IN ({placeholders})
        """, tuple(watched))
    else:
        candidates = read("""
            SELECT subject_id, title, poster_url, slug, rating, year, badge,
                   is_movie, is_tv, is_anime, subject_type, genre
            FROM subjects
            WHERE (is_movie = 1 OR is_tv = 1)
              AND CAST(rating AS REAL) >= 6
              AND genre IS NOT NULL
              AND genre != ''
        """)

    scored = []
    for c in candidates:
        c_genres = {g.strip().lower() for g in (c["genre"] or "").split(",") if g.strip()}
        overlap = c_genres & top_genres
        if not overlap:
            continue
        score = len(overlap) * 2.0 + _rating_boost(c["rating"])
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    return [_rec_item(c) for _, c in scored[:limit]]


def recommend_because(slug: str, limit: int = 12) -> dict:
    """Return 'because you watched {slug}' recommendations. When the source
    has no genre yet (enrichment hasn't run), falls back to top-rated
    unwatched of the same type so the section isn't empty."""
    src_rows = read(
        "SELECT title, poster_url, genre, is_movie, is_tv FROM subjects WHERE slug=?",
        (slug,),
    )
    if not src_rows:
        return {"source": slug, "title": None, "items": []}
    src = src_rows[0]
    src_genres = {g.strip().lower() for g in (src["genre"] or "").split(",") if g.strip()}

    if not src_genres:
        # Source has no genre — fall back to top-rated of same type
        if src["is_movie"]:
            type_where = "is_movie = 1"
        elif src["is_tv"]:
            type_where = "is_tv = 1"
        else:
            type_where = "(is_movie = 1 OR is_tv = 1)"
        rows = read(f"""
            SELECT subject_id, title, poster_url, slug, rating, year, badge,
                   is_movie, is_tv, is_anime, subject_type, genre
            FROM subjects
            WHERE slug != ?
              AND {type_where}
              AND CAST(rating AS REAL) >= 7
            ORDER BY CAST(rating AS REAL) DESC
            LIMIT ?
        """, (slug, limit))
        return {
            "source": slug,
            "title": src["title"],
            "poster_url": src["poster_url"],
            "items": [_rec_item(r) for r in rows],
        }

    candidates = read("""
        SELECT subject_id, title, poster_url, slug, rating, year, badge,
               is_movie, is_tv, is_anime, subject_type, genre
        FROM subjects
        WHERE slug != ?
          AND (is_movie = 1 OR is_tv = 1)
          AND genre IS NOT NULL
          AND genre != ''
    """, (slug,))

    scored = []
    for c in candidates:
        c_genres = {g.strip().lower() for g in (c["genre"] or "").split(",") if g.strip()}
        overlap = c_genres & src_genres
        if not overlap:
            continue
        score = len(overlap) * 2.0 + _rating_boost(c["rating"])
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    return {
        "source": slug,
        "title": src["title"],
        "poster_url": src["poster_url"],
        "items": [_rec_item(c) for _, c in scored[:limit]],
    }
