import re


_TS_RE = re.compile(r"^(\d{1,2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}),(\d{3})(.*)$")
_INDEX_RE = re.compile(r"^\d+$")


def normalize_banner_item(item: dict) -> dict | None:
    subject = item.get("subject") or {}
    title = item.get("title") or subject.get("title")
    if not title or "Communities" in title:
        return None
    return {
        "name": title,
        "poster_url": (item.get("image") or {}).get("url") or (subject.get("cover") or {}).get("url"),
        "slug": item.get("detailPath") or subject.get("detailPath"),
        "subject_id": subject.get("subjectId"),
        "badge": subject.get("corner"),
    }


def normalize_subject_item(sub: dict) -> dict | None:
    return {
        "name": sub.get("title"),
        "poster_url": (sub.get("cover") or {}).get("url"),
        "slug": sub.get("detailPath"),
        "subject_id": sub.get("subjectId"),
        "badge": sub.get("corner"),
        "rating": sub.get("imdbRatingValue"),
    }


def srt_to_vtt(srt: str) -> str:
    text = srt.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = ["WEBVTT", ""]
    for line in text.split("\n"):
        stripped = line.strip()
        if _INDEX_RE.match(stripped):
            continue
        m = _TS_RE.match(stripped)
        if m:
            out.append(f"{m.group(1)}.{m.group(2)} --> {m.group(3)}.{m.group(4)}{m.group(5)}")
            continue
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def pick_mp4_stream(streams: list, res: str) -> dict | None:
    if not streams:
        return None
    if res == "best" or not res:
        return max(streams, key=lambda s: s.get("resolutions") or 0)
    target = res[:-1] if res.endswith("p") else res
    for s in streams:
        if str(s.get("resolutions")) == target:
            return s
    return None