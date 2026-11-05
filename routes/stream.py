"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
import state
import upstream
from config import PLAYER_HEADERS
from helpers import srt_to_vtt, pick_mp4_stream

router = APIRouter()


@router.get("/api/stream/{subject_id}")
async def get_stream_sources(subject_id: str, detail_path: str, se: int = 1, ep: int = 1):
    stream = await upstream.resolve_stream(subject_id, detail_path, se, ep)
    data = stream["data"]
    has_resource = data.get("hasResource", False)
    streams = [
        {
            "resolution": f"{s.get('resolutions')}p" if s.get("resolutions") else None,
            "format": s.get("format"),
            "url": s.get("url"),
            "size": s.get("size"),
            "duration": s.get("duration"),
            "codec": s.get("codecName"),
        }
        for s in data.get("streams", []) or []
    ]
    resolved_se = stream.get("resolved_se", se)
    resolved_ep = stream.get("resolved_ep", ep)
    fell_back = (resolved_se != se) or (resolved_ep != ep)
    return {
        "subject_id": subject_id,
        "se": resolved_se,
        "ep": resolved_ep,
        "requested_se": se,
        "requested_ep": ep,
        "fell_back_to_movie": fell_back,
        "has_resource": has_resource,
        "sources": streams,
        "hls": data.get("hls", []) or [],
        "dash": data.get("dash", []) or [],
        "free_episodes": data.get("freeNum"),
        "limited": data.get("limited", False),
        "note": None if has_resource else "No stream found for this episode.",
    }


@router.get("/api/stream/{subject_id}/captions")
async def get_captions(subject_id: str, detail_path: str, se: int = 1, ep: int = 1):
    stream = await upstream.resolve_stream(subject_id, detail_path, se, ep)
    captions = await upstream.resolve_captions(subject_id, detail_path, se, ep)
    return {
        "subject_id": subject_id,
        "se": stream.get("resolved_se", se),
        "ep": stream.get("resolved_ep", ep),
        "count": len(captions),
        "captions": captions,
    }


@router.get("/api/stream/{subject_id}/proxy")
async def proxy_stream(
    subject_id: str,
    request: Request,
    detail_path: str,
    se: int = 1,
    ep: int = 1,
    res: str = "best",
):
    stream = await upstream.resolve_stream(subject_id, detail_path, se, ep)
    data = stream["data"]
    picked = pick_mp4_stream(data.get("streams") or [], res)
    if not picked:
        raise HTTPException(502, detail=f"No MP4 source for res={res}.")
    stream_url = picked.get("url")
    if not stream_url:
        raise HTTPException(502, detail="Selected source has no URL")

    req_headers = {**PLAYER_HEADERS, "Referer": stream["referer"]}
    if (range_header := request.headers.get("range")):
        req_headers["Range"] = range_header

    client = state.require_client()
    upstream_req = client.build_request("GET", stream_url, headers=req_headers)
    upstream_resp = await client.send(upstream_req, stream=True)
    if upstream_resp.status_code >= 400:
        await upstream_resp.aclose()
        raise HTTPException(502, detail=f"Upstream stream error: {upstream_resp.status_code}")

    async def body_iter():
        try:
            async for chunk in upstream_resp.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await upstream_resp.aclose()

    fwd = {
        h: upstream_resp.headers[h]
        for h in ("content-length", "content-type", "accept-ranges",
                  "content-range", "etag", "last-modified")
        if h in upstream_resp.headers
    }

    return StreamingResponse(
        body_iter(),
        status_code=upstream_resp.status_code,
        headers=fwd,
        media_type=upstream_resp.headers.get("content-type", "video/mp4"),
    )


@router.get("/api/stream/{subject_id}/subtitles/{lang}")
async def get_subtitles_vtt(subject_id: str, lang: str, detail_path: str, se: int = 1, ep: int = 1):
    captions = await upstream.resolve_captions(subject_id, detail_path, se, ep)
    match = next((c for c in captions if (c.get("lan") or "").lower() == lang.lower()), None)
    if not match:
        raise HTTPException(404, detail=f"No caption for language: {lang}")
    srt_url = match.get("url")
    if not srt_url or not srt_url.startswith("https://"):
        raise HTTPException(502, detail="Invalid caption URL")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(srt_url)
    if r.status_code != 200:
        raise HTTPException(502, detail=f"Caption fetch failed: {r.status_code}")
    return Response(
        content=srt_to_vtt(r.text),
        media_type="text/vtt",
        headers={"Content-Disposition": f'inline; filename="{lang}.vtt"'},
    )
