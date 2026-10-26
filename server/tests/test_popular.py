import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.jobs import Settings
from server.provider import Provider, ProviderError


@pytest.mark.asyncio
async def test_daily_movies_keep_source_order_and_reject_untrusted_posters():
    provider = Provider()
    def card(slug, poster, title='Test', kind='movie'):
        return f'<a class="cb-top10-item" href="/{kind}/{slug}"><img alt="{title}" src="{poster}"></a>'
    image = 'https://image.tmdb.org/t/p/w185/Poster123.jpg'
    body = ('<a href="/movie/outside">Ignore unrelated recommendations</a><div id="cbTop10">'
            + card('series-first', image, kind='tv')
            + card('bad-poster', 'https://image.tmdb.org.evil.example/t/p/w185/X.jpg')
            + card('../escape', image)
            + card('first-movie', image, 'First &amp; foremost')
            + card('first-movie', image, 'Duplicate')
            + card('tracking-image', image+'?track=visitor')
            + ''.join(card(f'movie-{n}', image, f'Title {n}') for n in range(6)) + '</div>')
    async def fetch(url, limit=0):
        assert url == 'https://streamimdb.ru/'
        return body.encode()
    provider.fetch = fetch
    try:
        results = await provider.popular()
        assert [x['slug'] for x in results] == ['first-movie', 'movie-0', 'movie-1', 'movie-2']
        assert results[0]['title'] == 'First & foremost'
        assert {x['poster'] for x in results} == {'https://image.tmdb.org/t/p/w342/Poster123.jpg'}
    finally:
        await provider.close()


def test_popular_cache_refreshes_and_source_outage_does_not_break_search(tmp_path, monkeypatch):
    class Source:
        calls = 0
        fail = False
        async def popular(self):
            self.calls += 1
            if self.fail:
                raise ProviderError('source_unavailable')
            return [{'slug':'test-movie','title':'Test','poster':'https://image.tmdb.org/t/p/w342/Poster.jpg'}]
        async def search(self, query):
            return [{'slug':'search-result','title':'Still available'}]
        async def close(self):
            pass
    source = Source()
    now = [100000]
    monkeypatch.setattr('server.app.time.time', lambda: now[0])
    with TestClient(create_app(Settings(tmp_path), source)) as client:
        first = client.get('/api/cinema/popular')
        assert first.status_code == 200 and len(first.json()['results']) == 1
        assert client.get('/api/cinema/popular').json() == first.json()
        assert source.calls == 1
        now[0] += 901
        client.get('/api/cinema/popular')
        assert source.calls == 2
        source.fail = True
        now[0] += 901
        assert client.get('/api/cinema/popular').json() == {'results': []}
        assert client.get('/api/cinema/search?q=test').json()['results'][0]['slug'] == 'search-result'


@pytest.mark.asyncio
async def test_player_api_registers_only_scoped_manifest_hosts(monkeypatch):
    import json

    from server.provider import allowed_url, parse_media_playlist

    provider = Provider()
    cdn = 'https://new-cinema-cdn.example/film/master.m3u8'
    async def fetch(url, limit=0):
        if url.startswith('https://streamimdb.ru/movie/'):
            return b'window.__cbCwMeta = {"type":"movie","id":123,"title":"Test"};'
        if url.startswith('https://rest.opensubtitles.org/search/query-test'):
            return b'[]'
        assert url == 'https://streamdata.vaplayer.ru/api.php?tmdb=123&type=movie'
        return json.dumps({'status_code':200,'data':{'stream_urls':[cdn]},'default_subs':[]}).encode()
    provider.fetch = fetch
    try:
        with pytest.raises(ProviderError, match='source_url_rejected'):
            allowed_url(cdn, provider.media_hosts)
        movie = await provider.movie('test-film')
        assert movie['streams'] == [cdn]
        assert allowed_url(cdn, provider.media_hosts) == cdn
        playlist = '#EXTM3U\n#EXTINF:5,\npart.ts\n#EXT-X-ENDLIST'
        assert parse_media_playlist(playlist, cdn, provider.media_hosts) == [(5, 'https://new-cinema-cdn.example/film/part.ts')]
        with pytest.raises(ProviderError, match='source_url_rejected'):
            parse_media_playlist(playlist.replace('part.ts','https://unregistered.example/part.ts'), cdn, provider.media_hosts)
        for value in ['http://new-cinema-cdn.example/a.m3u8','https://127.0.0.1/a.m3u8',
                      'https://localhost/a.m3u8','https://[::1]/a.m3u8',
                      'https://user:secret@new-cinema-cdn.example/a.m3u8',
                      'https://new-cinema-cdn.example:8443/a.m3u8','https://new-cinema-cdn.example/arbitrary.html']:
            with pytest.raises(ProviderError, match='stream_unavailable'):
                provider.register_streams([value])
        # Even a domain from the player API cannot turn into an internal request.
        monkeypatch.setattr('server.provider.socket.getaddrinfo', lambda *a: [(2, 1, 6, '', ('127.0.0.1', 443))])
        with pytest.raises(ProviderError, match='source_address_rejected'):
            await provider._fetch(cdn, 1000)
        provider.media_hosts = {f'cdn-{n}.example' for n in range(128)}
        with pytest.raises(ProviderError, match='stream_unavailable'):
            provider.register_streams([cdn])
    finally:
        await provider.close()
