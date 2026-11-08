from fastapi import APIRouter, HTTPException
import upstream
from config import DEFAULT_HOST
from helpers import normalize_banner_item, normalize_subject_item

router = APIRouter()


@router.get("/home")
async def get_home(host: str = DEFAULT_HOST):
    ops = await upstream.get_home_operating_list(host)
    sections = []
    for op in ops:
        op_type = op.get("type")
        title = op.get("title", "Featured")
        if op_type == "BANNER":
            items = [
                n for n in (
                    normalize_banner_item(i)
                    for i in op.get("banner", {}).get("items", []) or []
                ) if n
            ]
            sections.append({"section": "Banner", "count": len(items), "items": items})
        elif op_type in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            items = [
                n for n in (
                    normalize_subject_item(s)
                    for s in op.get("subjects", []) or []
                ) if n
            ]
            sections.append({"section": title, "count": len(items), "items": items})
    return {"status": "success", "host": host, "sections": sections}


@router.get("/home/all")
async def get_home_aggregate(dedupe: bool = True, host: str = DEFAULT_HOST):
    ops = await upstream.get_home_operating_list(host)
    items: list[dict] = []
    seen: set[str] = set()
    for op in ops:
        op_type = op.get("type")
        if op_type == "BANNER":
            for raw in op.get("banner", {}).get("items", []) or []:
                norm = normalize_banner_item(raw)
                if not norm or not norm.get("subject_id"):
                    continue
                if dedupe and norm["subject_id"] in seen:
                    continue
                seen.add(norm["subject_id"])
                items.append(norm)
        elif op_type in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            for raw in op.get("subjects", []) or []:
                norm = normalize_subject_item(raw)
                if not norm or not norm.get("subject_id"):
                    continue
                if dedupe and norm["subject_id"] in seen:
                    continue
                seen.add(norm["subject_id"])
                items.append(norm)
    return {"count": len(items), "host": host, "items": items}


@router.get("/sections")
async def list_sections(host: str = DEFAULT_HOST):
    ops = await upstream.get_home_operating_list(host)
    out = []
    for op in ops:
        op_type = op.get("type")
        title = op.get("title", "Featured")
        if op_type == "BANNER":
            count = len(op.get("banner", {}).get("items", []) or [])
        elif op_type in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            count = len(op.get("subjects", []) or [])
        else:
            count = 0
        out.append({"section": title, "type": op_type, "count": count})
    return {"host": host, "sections": out}


@router.get("/browse/{section}")
async def browse_section(section: str, page: int = 1, per_page: int = 24, host: str = DEFAULT_HOST):
    ops = await upstream.get_home_operating_list(host)
    matched: list[dict] = []
    matched_titles: set[str] = set()
    for op in ops:
        op_type = op.get("type")
        title = op.get("title", "")
        if section.lower() not in title.lower():
            continue
        if op_type not in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
            continue
        matched_titles.add(title)
        for raw in op.get("subjects", []) or []:
            item = normalize_subject_item(raw)
            if item and item.get("subject_id"):
                matched.append(item)
    if not matched:
        raise HTTPException(404, detail=f"No section matching: {section!r}. Try /sections.")
    start = (page - 1) * per_page
    return {
        "section": section,
        "host": host,
        "matched_titles": sorted(matched_titles),
        "page": page,
        "per_page": per_page,
        "total": len(matched),
        "items": matched[start:start + per_page],
    }