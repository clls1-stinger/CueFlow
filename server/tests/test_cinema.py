import asyncio
import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.jobs import Jobs, Settings, command, webvtt
from server.provider import Provider, ProviderError, allowed_url, parse_media_playlist


@pytest.mark.parametrize("url", [
    "http://onlinecoursecreator.site/video", "https://127.0.0.1/video",
    "https://onlinecoursecreator.site.evil.example/video", "https://user@onlinecoursecreator.site/video",
    "https://onlinecoursecreator.site:8080/video", "file:///etc/passwd",
])
def test_never_fetches_unapproved_urls(url):
    with pytest.raises(ProviderError):
        allowed_url(url)


def test_hls_rejects_private_segments_and_nested_resources():
    source = "#EXTM3U\n#EXTINF:5,\nhttps://127.0.0.1/secret\n#EXT-X-ENDLIST"
    with pytest.raises(ProviderError):
        parse_media_playlist(source, "https://onlinecoursecreator.site/master.m3u8")
    with pytest.raises(ProviderError, match="stream_format_unsupported"):
        parse_media_playlist(source + '\n#EXT-X-KEY:URI="file:///secret"', "https://onlinecoursecreator.site/x")
    good = source.replace("https://127.0.0.1/secret", "part.ts")
    assert parse_media_playlist(good, "https://onlinecoursecreator.site/film/list.m3u8") == [
        (5, "https://onlinecoursecreator.site/film/part.ts")]


@pytest.mark.asyncio
async def test_catalog_reads_nested_cards_and_ignores_external_links():
    provider = Provider()
    async def fetch(url, limit=0):
        return b'<div class="cb-card"><a href="/movie/test-film"><h3 class="cb-card-title">Test &amp; title</h3><p class="cb-card-meta">2026</p></a></div><a class="cb-card" href="https://evil.example/movie/x">Bad</a>'
    provider.fetch = fetch
    try:
        assert await provider.search("test") == [{"slug":"test-film", "title":"Test & title", "meta":"2026"}]
    finally:
        await provider.close()


def ready_job(jobs, touched=None):
    token = secrets.token_urlsafe(32)
    jobs.folder(token).mkdir()
    jobs.entries[token] = {"slug":"test-movie","title":"Test", "created":time.time(),
        "touched":touched or time.time(), "state":"ready", "progress":100, "language":"en",
        "translated_language":None,"result":None,"error":None}
    (jobs.folder(token) / "movie.mp4").write_bytes(b"0123456789")
    jobs.persist(token)
    return token


@pytest.mark.asyncio
async def test_retention_survives_restart_and_cleans_expired_files(tmp_path):
    settings = Settings(tmp_path, idle_seconds=10)
    jobs = Jobs(settings, None)
    token = ready_job(jobs)
    restored = Jobs(settings, None)
    restored.load()
    assert restored.get(token)["state"] == "ready"
    restored.entries[token]["touched"] -= 20
    with pytest.raises(KeyError):
        restored.get(token)
    await restored.cleanup()
    assert not restored.folder(token).exists()
    interrupted = ready_job(jobs)
    jobs.entries[interrupted]["state"] = "downloading"
    jobs.persist(interrupted)
    restored.load()
    assert restored.get(interrupted)["error"] == "interrupted"
    assert not (restored.folder(interrupted) / "movie.mp4").exists()


def test_heartbeat_cannot_extend_absolute_expiry(tmp_path):
    jobs = Jobs(Settings(tmp_path, idle_seconds=100, max_age_seconds=20), None)
    token = ready_job(jobs)
    jobs.entries[token]["created"] -= 21
    with pytest.raises(KeyError):
        jobs.get(token, touch=True)


@pytest.mark.asyncio
async def test_cancel_removes_files_and_stops_processing(tmp_path):
    jobs = Jobs(Settings(tmp_path), None)
    token = ready_job(jobs)
    cancelled = asyncio.Event()
    async def processing():
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()
    jobs.tasks[token] = asyncio.create_task(processing())
    await asyncio.sleep(0)
    await jobs.remove(token)
    assert cancelled.is_set() and token not in jobs.entries
    assert not jobs.folder(token).exists()


@pytest.mark.asyncio
async def test_translation_preserves_synchronized_times(tmp_path):
    jobs = Jobs(Settings(tmp_path), None)
    token = ready_job(jobs)
    original = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
    (jobs.folder(token) / "subtitles.srt").write_text(original)
    with pytest.raises(ProviderError, match="translation_timing_changed"):
        await jobs.translate(token, original.replace("01,000", "02,000"), "es")
    assert not (jobs.folder(token) / "translated.srt").exists()


def test_vtt_escapes_provider_markup_but_keeps_languages():
    text = '1\n00:00:01,000 --> 00:00:03,000\n<i>明日</i> <script>alert(1)</script> & مرحبًا\n'
    converted = webvtt(text)
    assert "<script>" not in converted and "<i>" not in converted
    assert "明日" in converted and "مرحبًا" in converted and "&amp;" in converted
    assert "00:00:01.000 --> 00:00:03.000" in converted


class FakeProvider:
    async def close(self):
        pass


def test_api_capability_range_delete_and_bounded_body(tmp_path):
    app = create_app(Settings(tmp_path), FakeProvider())
    with TestClient(app) as client:
        token = ready_job(app.state.jobs)
        route = f"/api/cinema/jobs/{token}"
        response = client.get(route + "/files/movie.mp4", headers={"Range":"bytes=2-5"})
        assert response.status_code == 206 and response.content == b"2345"
        assert "no-store" in response.headers["cache-control"]
        assert client.get(route + "/files/state.json").status_code == 404
        assert client.get("/api/cinema/jobs/guess").status_code == 410
        assert client.post("/api/cinema/jobs", content=b"x" * 5000).status_code == 413
        assert client.post(route + "/heartbeat").status_code == 200
        assert client.delete(route).status_code == 204
        assert client.get(route).status_code == 410
        assert not app.state.jobs.folder(token).exists()


@pytest.mark.asyncio
async def test_subprocess_cancellation_kills_child(tmp_path):
    import sys
    marker = tmp_path / "unexpected"
    process = asyncio.create_task(command(sys.executable, "-c",
        "import time,pathlib;time.sleep(1);pathlib.Path(" + repr(str(marker)) + ").write_text('late')"))
    await asyncio.sleep(.1)
    process.cancel()
    with pytest.raises(asyncio.CancelledError):
        await process
    await asyncio.sleep(1)
    assert not marker.exists()


@pytest.mark.asyncio
async def test_real_media_pipeline_aligns_and_embeds_subtitles(tmp_path):
    import subprocess

    import srt

    from cueflow.smoke import fixture

    source = tmp_path / "fixture"
    source.mkdir()
    wav, subs = fixture(source)
    manifest = source / "input.m3u8"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        "color=c=black:s=160x90:r=24", "-i", str(wav), "-shortest", "-c:v", "libx264",
        "-preset", "ultrafast", "-c:a", "aac", "-hls_time", "5", "-hls_list_size", "0",
        str(manifest)], check=True, timeout=30)
    segments = parse_media_playlist(manifest.read_text(), "https://onlinecoursecreator.site/input.m3u8")
    class FixtureProvider:
        async def subtitle(self, item):
            return subs.read_bytes()
        async def playlist(self, url, height):
            return segments, url
        async def fetch(self, url, limit):
            return (source / url.rsplit("/", 1)[1]).read_bytes()
    root = tmp_path / "jobs"
    settings = Settings(root, min_free_bytes=0, max_media_bytes=100_000_000)
    jobs = Jobs(settings, FixtureProvider())
    jobs.load()
    movie = {"slug":"original-test", "title":"Original fixture", "streams":["fixture"],
        "subtitles":[{"id":"fixture", "name":"Original", "language":"en", "format":"srt"}]}
    token = await jobs.create(movie, "fixture")
    await jobs.tasks[token]
    entry = jobs.get(token)
    assert entry["state"] == "ready", entry
    assert entry["result"]["offset"] == pytest.approx(-2, abs=.5)
    folder = jobs.folder(token)
    assert [c.content for c in srt.parse((folder / "subtitles.srt").read_text())] == [
        c.content for c in srt.parse(subs.read_text())]
    output = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(folder / "movie.mp4")]))
    assert {s["codec_type"] for s in output["streams"]} == {"video", "audio", "subtitle"}
    assert not (folder / "segments").exists()
    await jobs.remove(token)
