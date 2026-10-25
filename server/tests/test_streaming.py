import asyncio

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.jobs import Settings
from server.segments import DownloadGate, SegmentCache
from server.tests.test_cinema import FakeProvider, ready_job


@pytest.mark.asyncio
async def test_seek_precedes_background_and_duplicate_requests_share_bytes(tmp_path):
    gate = DownloadGate(1)
    await gate.acquire(0)
    order = []
    class Source:
        async def fetch(self, url, limit):
            order.append(url)
            return b'G' + bytes(187)
    cache = SegmentCache(Source(), gate, tmp_path, [(5, 'begin'), (5, 'seek')], 1000, lambda *_: None)
    background = asyncio.create_task(cache.get(0, priority=5))
    await asyncio.sleep(.01)
    seek = asyncio.create_task(cache.get(1, priority=0))
    duplicate = asyncio.create_task(cache.get(1, priority=0))
    await asyncio.sleep(.01)
    gate.release()
    paths = await asyncio.gather(background, seek, duplicate)
    assert order == ['seek', 'begin']
    assert paths[1] == paths[2]
    assert cache.size == 376
    assert gate.available == 1
    await cache.close()


@pytest.mark.asyncio
async def test_aborted_viewer_does_not_cancel_export_and_close_stops_fetch(tmp_path):
    fetching, release = asyncio.Event(), asyncio.Event()
    class Source:
        async def fetch(self, url, limit):
            fetching.set()
            await release.wait()
            return b'G' + bytes(187)
    cache = SegmentCache(Source(), DownloadGate(1), tmp_path, [(5, 'part')], 1000, lambda *_: None)
    viewer = asyncio.create_task(cache.get(0))
    await fetching.wait()
    viewer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await viewer
    export = asyncio.create_task(cache.get(0, priority=5))
    release.set()
    assert (await export).read_bytes() == b'G' + bytes(187)
    await cache.close()
    assert not cache.tasks


def test_manifest_segments_and_captions_available_before_full_export(tmp_path):
    app = create_app(Settings(tmp_path), FakeProvider())
    class Source:
        async def fetch(self, url, limit):
            return b'G' + bytes(187)
    with TestClient(app) as client:
        jobs = app.state.jobs
        token = ready_job(jobs)
        jobs.entries[token].update(state='downloading', stream_ready=True)
        (jobs.folder(token) / 'movie.mp4').unlink()
        (jobs.folder(token) / 'original.vtt').write_text('WEBVTT\n')
        jobs.media[token] = SegmentCache(Source(), jobs.download_gate, jobs.folder(token) / 'segments',
            [(5, 'https://private-upstream.example/secret')], 1000, lambda *_: None)
        base = f'/api/cinema/jobs/{token}'
        status = client.get(base).json()
        assert status['stream_ready'] and 'movie.mp4' not in status['files']
        manifest = client.get(base + '/stream.m3u8')
        assert manifest.status_code == 200
        assert 'segments/0.ts' in manifest.text and 'secret' not in manifest.text
        assert 'no-store' in manifest.headers['cache-control']
        assert client.get(base + '/segments/0.ts').content == b'G' + bytes(187)
        assert client.get(base + '/segments/999.ts').status_code == 404
        assert client.get(base + '/files/original.vtt').status_code == 200
        assert client.get(base + '/files/movie.mp4').status_code == 404
        assert client.delete(base).status_code == 204
        assert client.get(base + '/segments/0.ts').status_code == 410
        assert not jobs.folder(token).exists()
