from __future__ import annotations

import asyncio
import contextlib
import html
import json
import os
import re
import secrets
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import chardet
import pysubs2
import srt

from server.provider import Provider, ProviderError
from server.segments import DownloadGate, SegmentCache

TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
FILES = {"movie.mp4": "video/mp4", "subtitles.srt": "application/x-subrip",
         "subtitles.vtt": "text/vtt", "translated.mp4": "video/mp4",
         "translated.srt": "application/x-subrip", "translated.vtt": "text/vtt",
         "original.srt": "application/x-subrip", "original.vtt": "text/vtt",
         "preliminary.vtt": "text/vtt", "preliminary.srt": "application/x-subrip"}


@dataclass
class Settings:
    root: Path
    idle_seconds: int = 3600
    max_age_seconds: int = 21600
    max_jobs: int = 6
    max_active: int = 2
    max_media_bytes: int = 2 * 1024**3
    max_disk_bytes: int = 12 * 1024**3
    min_free_bytes: int = 6 * 1024**3

    @classmethod
    def environment(cls):
        return cls(Path(os.getenv("CUEFLOW_DATA", "/data/cueflow")),
            idle_seconds=int(os.getenv("CUEFLOW_IDLE_SECONDS", "3600")),
            max_age_seconds=int(os.getenv("CUEFLOW_MAX_AGE_SECONDS", "21600")))


def subtitle_text(raw: bytes, format_: str) -> str:
    encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding)
    except UnicodeError:
        text = raw.decode(chardet.detect(raw).get("encoding") or "cp1252")
    if format_ != "srt":
        text = pysubs2.SSAFile.from_string(text, format_=format_).to_string("srt")
    cues = list(srt.parse(text))
    if not 3 <= len(cues) <= 10000 or any(c.start >= c.end or c.start.total_seconds() < 0 for c in cues):
        raise ProviderError("subtitle_invalid")
    return srt.compose(cues)


def webvtt(text: str) -> str:
    # Render dialogue as text. Provider HTML must not become active cue markup.
    parts = ["WEBVTT\n"]
    for cue in srt.parse(text):
        a = srt.timedelta_to_srt_timestamp(cue.start).replace(",", ".")
        b = srt.timedelta_to_srt_timestamp(cue.end).replace(",", ".")
        content = html.escape(re.sub(r"<[^>]*>", "", cue.content))
        parts.append(f"{a} --> {b}\n{content}\n")
    return "\n".join(parts)


async def command(*args: str, timeout=600) -> str:
    # A separate process group lets expiry/cancellation terminate FFmpeg children too.
    with contextlib.ExitStack() as stack:
        import tempfile
        log = stack.enter_context(tempfile.TemporaryFile())
        process = await asyncio.create_subprocess_exec(*args, stdout=log, stderr=log,
            start_new_session=True, env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                "CUEFLOW_FFMPEG_DIR": str(Path(shutil.which("ffmpeg") or "/usr/bin/ffmpeg").parent)})
        try:
            await asyncio.wait_for(process.wait(), timeout)
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        log.seek(0, 2)
        log.seek(max(0, log.tell() - 32000))
        text = log.read().decode("utf-8", errors="replace")
        if process.returncode:
            # Paths and upstream URLs are deliberately not exposed through the API.
            raise ProviderError("processing_failed")
        return text


class Jobs:
    def __init__(self, settings: Settings, provider: Provider):
        self.settings, self.provider = settings, provider
        self.entries: dict[str, dict] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.media: dict[str, SegmentCache] = {}
        self.download_gate = DownloadGate(4)
        self.lock = asyncio.Lock()

    def folder(self, token):
        if not TOKEN.fullmatch(token):
            raise KeyError(token)
        return self.settings.root / token

    def expired(self, entry, now=None):
        now = time.time() if now is None else now
        return now >= min(entry["created"] + self.settings.max_age_seconds,
                          entry["touched"] + self.settings.idle_seconds)

    def persist(self, token):
        path = self.folder(token) / "state.json"
        temp = path.with_suffix(".new")
        temp.write_text(json.dumps(self.entries[token]), encoding="utf-8")
        temp.replace(path)

    def load(self):
        self.settings.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in self.settings.root.iterdir():
            if not TOKEN.fullmatch(path.name) or not path.is_dir() or path.is_symlink():
                continue
            try:
                entry = json.loads((path / "state.json").read_text())
                if self.expired(entry):
                    shutil.rmtree(path)
                    continue
                if entry["state"] not in ("ready", "error"):
                    # An interrupted job cannot resume from an incomplete media file.
                    shutil.rmtree(path)
                    path.mkdir(mode=0o700)
                    entry.update(state="error", error="interrupted", progress=0)
                self.entries[path.name] = entry
                self.persist(path.name)
            except (OSError, ValueError, KeyError, TypeError):
                shutil.rmtree(path)

    def disk_usage(self):
        return sum(p.stat().st_size for p in self.settings.root.rglob("*") if p.is_file())

    def capacity(self):
        active = sum(not t.done() for t in self.tasks.values())
        if active >= self.settings.max_active or len(self.entries) >= self.settings.max_jobs:
            raise ProviderError("queue_full")
        reserve = (active + 1) * self.settings.max_media_bytes * 2
        if (self.disk_usage() + reserve > self.settings.max_disk_bytes
                or shutil.disk_usage(self.settings.root).free < reserve + self.settings.min_free_bytes):
            raise ProviderError("storage_full")

    async def create(self, movie: dict, subtitle_id: str, height=480):
        subtitle = next((s for s in movie["subtitles"] if s["id"] == subtitle_id), None)
        if not subtitle:
            raise ProviderError("subtitle_missing")
        async with self.lock:
            self.capacity()
            token = secrets.token_urlsafe(32)
            self.folder(token).mkdir(mode=0o700)
            self.entries[token] = {"slug": movie["slug"], "title": movie["title"],
                "language": subtitle["language"], "subtitle_name": subtitle["name"],
                "created": time.time(), "touched": time.time(), "state": "downloading",
                "progress": 0, "bytes": 0, "error": None, "result": None,
                "translated_language": None, "sync_status": "pending", "stream_ready": False}
            self.persist(token)
            self.tasks[token] = asyncio.create_task(self.prepare(token, movie, subtitle, height))
        return token

    def get(self, token, touch=False):
        self.folder(token)
        entry = self.entries[token]
        if self.expired(entry):
            raise KeyError(token)
        if touch:
            entry["touched"] = time.time()
            self.persist(token)
        return entry

    def public(self, token):
        entry = self.get(token)
        return {**entry, "token": token, "stream_ready": token in self.media and entry.get("stream_ready", False),
            "expires_at": min(entry["created"] + self.settings.max_age_seconds,
                              entry["touched"] + self.settings.idle_seconds),
            "idle_seconds": self.settings.idle_seconds,
            "files": [name for name in FILES if (self.folder(token) / name).is_file()]}

    def phase(self, token, state, progress):
        self.entries[token].update(state=state, progress=progress)
        self.persist(token)

    async def preview_alignment(self, token, text, cache):
        """Sample early dialogue; failure leaves original captions and the full scan."""
        folder = self.folder(token)
        cues = list(srt.parse(text))
        # A dense early window provides evidence without downloading the whole film.
        candidates = []
        for start in range(0, min(600, max(1, int(self.entries[token]["duration"] - 120))), 30):
            count = sum(start + 16 <= c.start.total_seconds()
                        and c.end.total_seconds() <= start + 104 for c in cues)
            if count >= 6:
                candidates.append((count, -start, start))
        if not candidates:
            return
        start = max(candidates)[2]
        end, indices, cursor, actual_start = start + 120, [], 0, None
        for index, (duration, _) in enumerate(cache.segments):
            if cursor < end and cursor + duration > start:
                if actual_start is None:
                    actual_start = cursor
                indices.append(index)
            cursor += duration
        try:
            async with asyncio.timeout(90):
                # Bounded workers prevent a sample from filling the gate's queue.
                remaining = iter(indices)
                async def worker():
                    for index in remaining:
                        await cache.get(index, priority=1)
                async with asyncio.TaskGroup() as group:
                    for _ in range(2):
                        group.create_task(worker())
                manifest = cache.folder / "sample.m3u8"
                manifest.write_text(cache.manifest(indices), encoding="utf-8")
                result = await command(sys.executable, "-m", "server.quick_sync", str(manifest),
                    str(folder / "original.srt"), str(actual_start),
                    str(self.entries[token]["duration"]), str(folder / "preliminary.srt"), timeout=30)
                line = next(x for x in result.splitlines() if x.startswith("CUEFLOW_QUICK_RESULT "))
                metrics = json.loads(line.removeprefix("CUEFLOW_QUICK_RESULT "))
                if metrics.get("status") != "preliminary":
                    return
                aligned = (folder / "preliminary.srt").read_text(encoding="utf-8")
                (folder / "preliminary.vtt").write_text(webvtt(aligned), encoding="utf-8")
                self.entries[token].update(sync_status="preliminary", preliminary_result=metrics)
                self.persist(token)
        except (Exception, TimeoutError):
            # A sample is optional and never replaces verification of the full audio.
            self.entries[token]["sync_status"] = "pending"

    async def prepare(self, token, movie, subtitle, height):
        folder = self.folder(token)
        quick = None
        cache = None
        try:
            async with asyncio.timeout(2400):
                text = subtitle_text(await self.provider.subtitle(subtitle), subtitle["format"])
                (folder / "original.srt").write_text(text, encoding="utf-8")
                (folder / "original.vtt").write_text(webvtt(text), encoding="utf-8")
                segments = None
                for url in movie["streams"]:
                    try:
                        segments, _ = await self.provider.playlist(url, height)
                        break
                    except ProviderError:
                        continue
                if not segments:
                    raise ProviderError("stream_unavailable")
                self.entries[token]["duration"] = sum(d for d, _ in segments)
                def progress(completed, size):
                    self.entries[token].update(progress=round(completed / len(segments) * 75, 1), bytes=size)
                    if completed % 20 == 0:
                        self.persist(token)
                cache = self.media[token] = SegmentCache(self.provider, self.download_gate,
                    folder / "segments", segments, self.settings.max_media_bytes, progress)
                await cache.get(0)
                self.entries[token].update(stream_ready=True, stream_ready_seconds=round(
                    time.time() - self.entries[token]["created"], 2))
                self.persist(token)
                quick = asyncio.create_task(self.preview_alignment(token, text, cache))
                await cache.download_all()
                quick.cancel()
                await asyncio.gather(quick, return_exceptions=True)
                manifest = cache.folder / "local.m3u8"
                manifest.write_text(cache.manifest(), encoding="utf-8")
                self.phase(token, "synchronizing", 85)
                result = await command(sys.executable, "-m", "server.sync_worker",
                    str(manifest), str(folder / "original.srt"), str(folder), timeout=900)
                line = next((x for x in result.splitlines() if x.startswith("CUEFLOW_RESULT ")), None)
                if not line:
                    raise ProviderError("alignment_failed")
                metrics = json.loads(line.removeprefix("CUEFLOW_RESULT "))
                aligned = Path(metrics.pop("output"))
                text = aligned.read_text(encoding="utf-8")
                aligned.replace(folder / "subtitles.srt")
                (folder / "subtitles.vtt").write_text(webvtt(text), encoding="utf-8")
                self.entries[token].update(result=metrics, sync_status="verified")
                self.phase(token, "packaging", 95)
                await self.mux(token, "segments/local.m3u8", "subtitles.srt", "movie.mp4", subtitle["language"])
                self.phase(token, "ready", 100)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if quick:
                quick.cancel()
                await asyncio.gather(quick, return_exceptions=True)
            if cache:
                await cache.close()
            self.media.pop(token, None)
            if isinstance(exc, ExceptionGroup):
                while isinstance(exc, ExceptionGroup):
                    exc = exc.exceptions[0]
            error = "processing_failed"
            if isinstance(exc, ProviderError):
                error = str(exc)
            elif isinstance(exc, TimeoutError):
                error = "processing_timeout"
            shutil.rmtree(folder)
            folder.mkdir(mode=0o700)
            self.entries[token].update(state="error", error=error, stream_ready=False)
            self.persist(token)
        finally:
            if quick:
                quick.cancel()
                await asyncio.gather(quick, return_exceptions=True)

    async def mux(self, token, video, subtitle, output, language):
        folder = self.folder(token)
        target = folder / ("pending-" + output)
        await command("ffmpeg", "-nostdin", "-v", "error", "-y",
            "-protocol_whitelist", "file", "-i", str(folder / video),
            "-i", str(folder / subtitle), "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=" + {"en":"eng", "es":"spa", "ja":"jpn", "fr":"fra", "de":"deu", "it":"ita", "pt":"por", "pb":"por", "zh":"zho", "ru":"rus", "ar":"ara"}.get(language, language), "-movflags", "+faststart", str(target))
        target.replace(folder / output)

    async def translate(self, token, text, language):
        entry = self.get(token)
        if entry["state"] != "ready" or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", language):
            raise ProviderError("job_not_ready")
        original = list(srt.parse((self.folder(token) / "subtitles.srt").read_text()))
        translated = list(srt.parse(text))
        if len(original) != len(translated) or any(
            a.start != b.start or a.end != b.end or not b.content.strip()
            for a, b in zip(original, translated)
        ):
            raise ProviderError("translation_timing_changed")
        async with self.lock:
            if entry["state"] != "ready":
                raise ProviderError("job_not_ready")
            self.capacity_for_translation(token)
            folder = self.folder(token)
            text = srt.compose(translated)
            (folder / "pending-subtitles.srt").write_text(text, encoding="utf-8")
            (folder / "pending-subtitles.vtt").write_text(webvtt(text), encoding="utf-8")
            entry["error"] = None
            self.phase(token, "translating", 95)
            self.tasks[token] = asyncio.create_task(self.finish_translation(token, language))

    def capacity_for_translation(self, token):
        if (sum(not t.done() for t in self.tasks.values()) >= self.settings.max_active
                or self.disk_usage() + (self.folder(token) / "movie.mp4").stat().st_size > self.settings.max_disk_bytes
                or shutil.disk_usage(self.settings.root).free < self.settings.min_free_bytes + self.settings.max_media_bytes):
            raise ProviderError("storage_full")

    async def finish_translation(self, token, language):
        folder = self.folder(token)
        try:
            await self.mux(token, "movie.mp4", "pending-subtitles.srt", "translated.mp4", language)
            (folder / "pending-subtitles.srt").replace(folder / "translated.srt")
            (folder / "pending-subtitles.vtt").replace(folder / "translated.vtt")
            self.entries[token]["translated_language"] = language
        except asyncio.CancelledError:
            raise
        except Exception:
            self.entries[token]["error"] = "translation_packaging_failed"
        finally:
            for name in ("pending-subtitles.srt", "pending-subtitles.vtt", "pending-translated.mp4"):
                (folder / name).unlink(missing_ok=True)
            if token in self.entries:
                self.phase(token, "ready", 100)

    async def remove(self, token):
        self.folder(token)
        task = self.tasks.pop(token, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        cache = self.media.pop(token, None)
        if cache:
            await cache.close()
        self.entries.pop(token, None)
        shutil.rmtree(self.folder(token), ignore_errors=True)

    async def cleanup(self):
        for token, entry in list(self.entries.items()):
            if self.expired(entry):
                await self.remove(token)

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        await asyncio.gather(*(cache.close() for cache in self.media.values()))
