"""Bounded access to the catalog and the public APIs used by its player.

No user-supplied URL is fetched. Media manifests are parsed and every segment
is downloaded by this adapter; FFmpeg receives only local files.
"""
from __future__ import annotations

import asyncio
import gzip
import html
import io
import ipaddress
import json
import re
import socket
from urllib.parse import quote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,120}\Z")
HOSTS = frozenset({
    "streamimdb.ru", "streamdata.vaplayer.ru", "onlinecoursecreator.site",
    "rest.opensubtitles.org", "dl.opensubtitles.org", "vidapi.cloud",
})
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://nextgencloudfabric.com/",
    "Origin": "https://nextgencloudfabric.com",
    "X-User-Agent": "trailers.to-UA",
}


class ProviderError(Exception):
    pass


def allowed_url(url: str, media_hosts=()) -> str:
    p = urlsplit(url)
    if (p.scheme != "https" or (p.hostname not in HOSTS and p.hostname not in media_hosts)
            or p.port not in (None, 443)
            or p.username or p.password or p.fragment):
        raise ProviderError("source_url_rejected")
    return url


class Provider:
    def __init__(self):
        self.media_hosts = set()
        self.client = httpx.AsyncClient(
            headers=HEADERS, timeout=httpx.Timeout(30, connect=15),
            limits=httpx.Limits(max_connections=20), follow_redirects=False,
            trust_env=False,
        )

    async def close(self):
        await self.client.aclose()

    async def fetch(self, url: str, limit=2_000_000) -> bytes:
        try:
            return await self._fetch(url, limit)
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise ProviderError("source_unavailable") from exc

    async def _fetch(self, url: str, limit: int) -> bytes:
        for _ in range(4):
            allowed_url(url, self.media_hosts)
            host = urlsplit(url).hostname
            addresses = await asyncio.wait_for(
                asyncio.to_thread(socket.getaddrinfo, host, 443, 0, socket.SOCK_STREAM), 15)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ProviderError("source_address_rejected")
            async with self.client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                if response.status_code != 200:
                    raise ProviderError("source_unavailable")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ProviderError("source_too_large")
                return bytes(data)
        raise ProviderError("source_redirects")

    def register_streams(self, urls) -> list[str]:
        # Called only for manifest URLs returned by the fixed player API below.
        # Each request still resolves DNS and rejects non-public addresses.
        streams, hosts = [], set()
        for url in urls[:6]:
            if not isinstance(url, str):
                continue
            try:
                parsed = urlsplit(url)
                host = parsed.hostname or ""
                if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", host):
                    continue
                if not parsed.path.endswith(".m3u8"):
                    continue
                allowed_url(url, {host})
            except (ProviderError, ValueError):
                continue
            hosts.add(host)
            streams.append(url)
        if not streams or len(self.media_hosts | hosts) > 128:
            raise ProviderError("stream_unavailable")
        self.media_hosts.update(hosts)
        return streams

    async def search(self, query: str) -> list[dict]:
        body = await self.fetch("https://streamimdb.ru/search?q=" + quote(query))
        soup = BeautifulSoup(body, "html.parser")
        found = {}
        for card in soup.select(".cb-card a[href^='/movie/'], a.cb-card[href^='/movie/']"):
            href = card.get("href", "")
            slug = href.removeprefix("/movie/")
            title = card.select_one(".cb-card-title")
            if not href.startswith("/movie/") or not SLUG.fullmatch(slug) or not title:
                continue
            meta = card.select_one(".cb-card-meta")
            found[slug] = {"slug": slug, "title": title.get_text(" ", strip=True)[:200],
                           "meta": meta.get_text(" ", strip=True)[:100] if meta else ""}
        return list(found.values())[:40]

    async def popular(self) -> list[dict]:
        """Keep the order of the site's daily top movies, with bounded poster URLs."""
        soup = BeautifulSoup(await self.fetch("https://streamimdb.ru/"), "html.parser")
        found = {}
        for card in soup.select("#cbTop10 a.cb-top10-item[href^='/movie/']"):
            slug = card.get("href", "").removeprefix("/movie/")
            poster = card.select_one("img")
            if not SLUG.fullmatch(slug) or slug in found or not poster:
                continue
            title = poster.get("alt", "").strip()[:200]
            # Only static TMDB poster paths; never relay an arbitrary image URL.
            match = re.fullmatch(r"https://image\.tmdb\.org/t/p/(?:w\d+|original)/([A-Za-z0-9]+\.(?:jpg|png|webp))",
                                 poster.get("src", ""))
            if not title or not match:
                continue
            found[slug] = {"slug": slug, "title": title,
                           "poster": "https://image.tmdb.org/t/p/w342/" + match[1]}
            if len(found) == 4:
                break
        return list(found.values())

    async def movie(self, slug: str) -> dict:
        if not SLUG.fullmatch(slug):
            raise ProviderError("movie_invalid")
        body = (await self.fetch("https://streamimdb.ru/movie/" + slug)).decode("utf-8")
        match = re.search(r"window\.__cbCwMeta\s*=\s*(\{[^;]+\})\s*;", body)
        if not match:
            raise ProviderError("movie_unavailable")
        meta = json.loads(match[1])
        tmdb = str(meta.get("id", ""))
        if meta.get("type") != "movie" or not tmdb.isdigit():
            raise ProviderError("movie_invalid")
        info = json.loads(await self.fetch(
            f"https://streamdata.vaplayer.ru/api.php?tmdb={tmdb}&type=movie"))
        data = info.get("data", {})
        streams = data.get("stream_urls")
        if str(info.get("status_code")) != "200" or not isinstance(streams, list) or not streams:
            raise ProviderError("movie_unavailable")
        streams = self.register_streams(streams)
        imdb = str(data.get("imdb_id", ""))
        subtitles = []
        subtitle_error = False
        if re.fullmatch(r"tt\d{5,12}", imdb):
            try:
                candidates = json.loads(await self.fetch(
                    "https://rest.opensubtitles.org/search/imdbid-" + imdb[2:], 4_000_000))
                for item in candidates[:300]:
                    if item.get("SubFormat") not in ("srt", "ass", "ssa", "vtt"):
                        continue
                    code = str(item.get("ISO639", ""))
                    sid = str(item.get("IDSubtitleFile", ""))
                    if not sid.isdigit() or not re.fullmatch(r"[a-z]{2,3}", code):
                        continue
                    try:
                        url = allowed_url(item["SubDownloadLink"])
                    except (KeyError, ProviderError):
                        continue
                    subtitles.append({"id": "os-" + sid, "language": code,
                        "label": str(item.get("LanguageName", code))[:80],
                        "name": str(item.get("SubFileName", ""))[:220],
                        "format": item["SubFormat"], "url": url})
            except (ProviderError, ValueError, KeyError, TypeError):
                subtitle_error = True
        for index, item in enumerate(info.get("default_subs", [])[:30]):
            try:
                url = allowed_url(item["url"])
                code = str(item["code"])
                if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?", code):
                    continue
                subtitles.append({"id": f"embedded-{index}", "language": code,
                    "label": str(item.get("lang", code))[:80], "name": "StreamIMDB",
                    "format": "srt", "url": url})
            except (KeyError, ProviderError):
                continue
        release_words = set(re.findall(r"[a-z0-9]+", str(data.get("file_name", "")).lower()))
        subtitles.sort(key=lambda s: (
            -len(release_words & set(re.findall(r"[a-z0-9]+", s["name"].lower()))),
            s["format"] != "srt"))
        return {"slug": slug, "title": str(meta.get("title", ""))[:200],
                "imdb": imdb, "streams": streams, "subtitles": subtitles,
                "subtitle_search_unavailable": subtitle_error}

    async def playlist(self, url: str, height: int) -> tuple[list[tuple[float, str]], str]:
        # At most one master and one media playlist. Never hand remote URLs to FFmpeg.
        for depth in range(2):
            text = (await self.fetch(url, 1_000_000)).decode("utf-8-sig")
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            if not lines or lines[0] != "#EXTM3U":
                raise ProviderError("playlist_invalid")
            variants = []
            for i, line in enumerate(lines[:-1]):
                if line.startswith("#EXT-X-STREAM-INF:"):
                    size = re.search(r"RESOLUTION=\d+x(\d+)", line)
                    variants.append((int(size[1]) if size else 0, urljoin(url, lines[i+1])))
            if not variants:
                return parse_media_playlist(text, url, self.media_hosts), url
            if depth:
                raise ProviderError("playlist_invalid")
            under = [x for x in variants if x[0] <= height]
            url = (max(under) if under else min(variants))[1]
            allowed_url(url, self.media_hosts)
        raise ProviderError("playlist_invalid")

    async def subtitle(self, item: dict) -> bytes:
        data = await self.fetch(item["url"], 2_000_000)
        if data[:2] == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as file:
                data = file.read(2_000_001)
        if len(data) > 2_000_000:
            raise ProviderError("subtitle_too_large")
        return data


def parse_media_playlist(text: str, base: str, media_hosts=()) -> list[tuple[float, str]]:
    if "#EXT-X-ENDLIST" not in text:
        raise ProviderError("live_stream_unsupported")
    if any(tag in text for tag in ("#EXT-X-KEY", "#EXT-X-MAP", "#EXT-X-BYTERANGE")):
        raise ProviderError("stream_format_unsupported")
    segments = []
    duration = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            try:
                duration = float(line[8:].split(",")[0])
            except ValueError as exc:
                raise ProviderError("playlist_invalid") from exc
            if not 0 < duration <= 60:
                raise ProviderError("playlist_invalid")
        elif line and not line.startswith("#"):
            if duration is None:
                raise ProviderError("playlist_invalid")
            segments.append((duration, allowed_url(urljoin(base, html.unescape(line)), media_hosts)))
            duration = None
    if not segments or len(segments) > 4000 or sum(d for d, _ in segments) > 14400:
        raise ProviderError("movie_too_long")
    return segments
