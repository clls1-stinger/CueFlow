"""Shared, bounded segment downloads with playback ahead of background export."""
from __future__ import annotations

import asyncio
import contextlib
import heapq
import itertools
import math

from server.provider import ProviderError


class DownloadGate:
    def __init__(self, slots=4):
        self.available = slots
        self.waiting = []
        self.sequence = itertools.count()

    async def acquire(self, priority):
        if self.available and not self.waiting:
            self.available -= 1
            return
        future = asyncio.get_running_loop().create_future()
        heapq.heappush(self.waiting, (priority, next(self.sequence), future))
        try:
            await future
        except asyncio.CancelledError:
            if future.done() and not future.cancelled():
                self.release()
            future.cancel()
            raise

    def release(self):
        while self.waiting:
            _, _, future = heapq.heappop(self.waiting)
            if not future.done():
                future.set_result(None)
                return
        self.available += 1

    @contextlib.asynccontextmanager
    async def slot(self, priority):
        await self.acquire(priority)
        try:
            yield
        finally:
            self.release()


class SegmentCache:
    def __init__(self, provider, gate, folder, segments, maximum, progress):
        self.provider, self.gate, self.folder = provider, gate, folder
        self.segments, self.maximum, self.progress = segments, maximum, progress
        self.tasks = {}
        self.size, self.completed = 0, 0
        self.closed = False
        folder.mkdir(exist_ok=True)

    async def get(self, index, priority=0):
        if self.closed or not 0 <= index < len(self.segments):
            raise ProviderError("segment_unavailable")
        path = self.folder / f"{index}.ts"
        if path.is_file():
            return path
        task = self.tasks.get(index)
        if task is None:
            task = self.tasks[index] = asyncio.create_task(self.download(index, priority))
        # A browser abort must not cancel an export or another viewer using this segment.
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.tasks.pop(index, None)

    async def download(self, index, priority):
        for attempt in range(5):
            try:
                async with self.gate.slot(priority):
                    await asyncio.sleep(.25)
                    data = await self.provider.fetch(self.segments[index][1], 16_000_000)
                break
            except (ProviderError, OSError):
                if attempt == 4:
                    raise
                await asyncio.sleep(min(30, 2 ** (attempt + 1)))
        if self.closed:
            raise asyncio.CancelledError()
        if not data or data[0] != 0x47 or len(data) < 188:
            raise ProviderError("segment_invalid")
        if self.size + len(data) > self.maximum:
            raise ProviderError("movie_too_large")
        path = self.folder / f"{index}.ts"
        temporary = path.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(path)
        self.size += len(data)
        self.completed += 1
        self.progress(self.completed, self.size)
        return path

    def manifest(self, indices=None, remote=False):
        indices = list(range(len(self.segments))) if indices is None else list(indices)
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-PLAYLIST-TYPE:VOD",
                 "#EXT-X-MEDIA-SEQUENCE:0",
                 f"#EXT-X-TARGETDURATION:{math.ceil(max(self.segments[i][0] for i in indices))}"]
        for i in indices:
            lines.extend([f"#EXTINF:{self.segments[i][0]},", f"{'segments/' if remote else ''}{i}.ts"])
        return "\n".join(lines + ["#EXT-X-ENDLIST", ""])

    async def download_all(self):
        indices = iter(range(len(self.segments)))
        async def worker():
            for index in indices:
                await self.get(index, priority=5)
        async with asyncio.TaskGroup() as group:
            for _ in range(4):
                group.create_task(worker())

    async def close(self):
        self.closed = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
