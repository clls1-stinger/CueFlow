from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from server.jobs import FILES, Jobs, Settings
from server.provider import SLUG, Provider, ProviderError

PREFIX = "/api/cinema"
ORIGINS = ["https://cueflow.enriquepl.com", "https://cueflow-dhh.pages.dev"]


async def body_json(request: Request, maximum=4096):
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > maximum:
            raise HTTPException(413, "request_too_large")
    try:
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise HTTPException(400, "request_invalid") from None


def create_app(settings=None, provider=None):
    settings = settings or Settings.environment()
    provider = provider or Provider()
    jobs = Jobs(settings, provider)
    cache = OrderedDict()
    rates = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app):
        jobs.load()
        async def sweep():
            while True:
                await asyncio.sleep(30)
                await jobs.cleanup()
                now = time.time()
                for key, events in list(rates.items()):
                    if not events or events[-1] < now - 600:
                        rates.pop(key, None)
        cleaner = asyncio.create_task(sweep())
        yield
        cleaner.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleaner
        await jobs.close()
        await provider.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.jobs = jobs
    app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
        allow_methods=["GET", "POST", "DELETE", "HEAD"], allow_headers=["Content-Type", "Range"])

    @app.middleware("http")
    async def response_headers(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in ORIGINS and not os.getenv("CUEFLOW_DEV"):
            return JSONResponse({"detail": "origin_rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        code = str(exc)
        status = 429 if code in ("queue_full", "storage_full") else 502
        return JSONResponse({"detail": code}, status_code=status)

    @app.exception_handler(KeyError)
    async def expired_error(request, exc):
        return JSONResponse({"detail": "job_expired"}, status_code=410)

    def rate(request, kind, maximum):
        # Production has no published container port; traffic arrives via Cloudflare.
        ip = request.headers.get("cf-connecting-ip") or request.client.host
        key = (ip, kind)
        if len(rates) > 10000 and key not in rates:
            raise HTTPException(429, "rate_limit")
        events = rates[key]
        now = time.time()
        while events and events[0] < now - 600:
            events.popleft()
        if len(events) >= maximum:
            raise HTTPException(429, "rate_limit")
        events.append(now)

    async def movie(slug):
        if not SLUG.fullmatch(slug):
            raise HTTPException(400, "movie_invalid")
        record = cache.get(slug)
        if record and record[0] > time.time() - 300:
            return record[1]
        result = await provider.movie(slug)
        cache[slug] = (time.time(), result)
        cache.move_to_end(slug)
        while len(cache) > 128:
            cache.popitem(last=False)
        return result

    @app.get(PREFIX + "/health")
    async def health():
        return {"service": "CueFlow cinema", "commit": os.getenv("CUEFLOW_COMMIT", "development"),
            "idle_seconds": settings.idle_seconds, "max_age_seconds": settings.max_age_seconds,
            "max_active": settings.max_active, "max_media_bytes": settings.max_media_bytes}

    @app.get(PREFIX + "/search")
    async def search(request: Request, q: str = ""):
        rate(request, "read", 60)
        q = q.strip()
        if not 2 <= len(q) <= 120:
            raise HTTPException(400, "query_invalid")
        return {"results": await provider.search(q)}

    @app.get(PREFIX + "/movies/{slug}")
    async def detail(request: Request, slug: str):
        rate(request, "read", 60)
        result = await movie(slug)
        return {k: v for k, v in result.items() if k not in ("streams", "subtitles")} | {
            "subtitles": [{k: v for k, v in s.items() if k != "url"} for s in result["subtitles"]]}

    @app.post(PREFIX + "/jobs", status_code=202)
    async def create(request: Request):
        rate(request, "create", 6)
        body = await body_json(request)
        slug, subtitle = body.get("slug"), body.get("subtitle_id")
        height = body.get("height", 480)
        if not isinstance(slug, str) or not isinstance(subtitle, str) or height not in (480, 720):
            raise HTTPException(400, "request_invalid")
        result = await movie(slug)
        token = await jobs.create(result, subtitle, height)
        return jobs.public(token)

    @app.get(PREFIX + "/jobs/{token}")
    async def status(token: str):
        return jobs.public(token)

    @app.post(PREFIX + "/jobs/{token}/heartbeat")
    async def heartbeat(token: str):
        jobs.get(token, touch=True)
        return jobs.public(token)

    @app.delete(PREFIX + "/jobs/{token}", status_code=204)
    async def remove(token: str):
        jobs.get(token)
        await jobs.remove(token)

    @app.post(PREFIX + "/jobs/{token}/subtitles", status_code=202)
    async def subtitles(request: Request, token: str):
        body = await body_json(request, 1_250_000)
        if not isinstance(body.get("text"), str) or not isinstance(body.get("language"), str):
            raise HTTPException(400, "request_invalid")
        try:
            await jobs.translate(token, body["text"], body["language"])
        except (ValueError, TypeError):
            raise HTTPException(400, "subtitle_invalid") from None
        return jobs.public(token)

    @app.api_route(PREFIX + "/jobs/{token}/files/{name}", methods=["GET", "HEAD"])
    async def file(token: str, name: str, download: bool = False):
        entry = jobs.get(token)
        if name not in FILES or entry["state"] not in ("ready", "translating"):
            raise HTTPException(404, "file_unavailable")
        path = jobs.folder(token) / name
        if not path.is_file():
            raise HTTPException(404, "file_unavailable")
        return FileResponse(path, media_type=FILES[name],
            filename=entry["slug"] + "." + name if download else None,
            content_disposition_type="attachment" if download else "inline")

    return app


app = create_app()
