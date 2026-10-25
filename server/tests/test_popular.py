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
