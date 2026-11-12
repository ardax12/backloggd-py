from pathlib import Path
import httpx
import pytest
from backloggd import Backloggd, BackloggdClient, ChallengeResponseError, PageParseError

FIXTURES = Path(__file__).parent / "fixtures"
ACTIVITY = (FIXTURES / "millers_activity.html").read_text(encoding="utf-8")
JOURNAL = (FIXTURES / "millers_journal.html").read_text(encoding="utf-8")

def journal_page(body):
    return '<html><title>Millers journal</title><main>' + body + '</main></html>'

def transport(request):
    if '/activity/you/' in request.url.path:
        return httpx.Response(200, text=ACTIVITY)
    return httpx.Response(200, text=journal_page(JOURNAL))


def test_sync_activity_and_journal_public_apis():
    with Backloggd(cookies_file=None, cache_enabled=False) as client:
        client._client = httpx.Client(transport=httpx.MockTransport(transport))
        events = client.get_user_activity('https://backloggd.com/u/Millers/')
        assert events[0].occurred_at == '2026-11-11T15:48:38Z'
        assert events[0].rating == 3.0
        journal = client.get_user_journal('Millers', max_pages=100, require_complete=True)
        assert len(journal) == 30
        assert journal[0].session_labels == ('Finished',)
        assert journal[1].session_labels == ('Started',)

@pytest.mark.asyncio
async def test_async_activity_and_journal_public_apis():
    client = BackloggdClient(cookies_file=None, cache_enabled=False)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        assert len(await client.get_user_activity('Millers')) == 1
        journal = await client.get_user_journal('Millers', max_pages=100, require_complete=True)
        assert journal[0].played_date == 'November, 2026 11'
        assert journal[1].session_labels == ('Started',)
    finally:
        await client.close()

@pytest.mark.parametrize('body, error', [
    ('<title>Making sure you are not a bot!</title>', ChallengeResponseError),
    ('<title>Access denied</title><footer>BotStopper</footer>', ChallengeResponseError),
    ('<html>unexpected markup</html>', PageParseError),
])
def test_invalid_activity_is_not_an_empty_success(body, error):
    client = Backloggd(cookies_file=None, cache_enabled=False)
    client._client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)))
    try:
        with pytest.raises(error):
            client.get_user_activity('Millers')
    finally:
        client.close()

@pytest.mark.asyncio
async def test_later_journal_challenge_does_not_return_partial_history():
    def handler(request):
        if request.url.params.get('page') == '1':
            return httpx.Response(200, text=journal_page(JOURNAL + '<a rel="next" href="?page=2">Next</a>'))
        return httpx.Response(200, text='<title>Access denied</title><footer>BotStopper</footer>')
    client = BackloggdClient(cookies_file=None, cache_enabled=False, request_delay=0)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ChallengeResponseError):
            await client.get_user_journal('Millers', max_pages=100, require_complete=True)
    finally:
        await client.close()

@pytest.mark.parametrize('require_complete', [False, True])
def test_journal_limit_is_explicit(require_complete):
    body = journal_page(JOURNAL + '<a rel="next" href="?page=2">Next</a>')
    client = Backloggd(cookies_file=None, cache_enabled=False, request_delay=0)
    client._client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)))
    try:
        if require_complete:
            with pytest.raises(PageParseError):
                client.get_user_journal('Millers', max_pages=1, require_complete=True)
        else:
            assert len(client.get_user_journal('Millers', max_pages=1)) == 30
    finally:
        client.close()

@pytest.mark.asyncio
async def test_successful_empty_sources():
    def handler(request):
        body = '<div id="activities-list">No recent activity</div>' if '/activity/' in request.url.path else journal_page('No journal entries')
        return httpx.Response(200, text=body)
    client = BackloggdClient(cookies_file=None, cache_enabled=False)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await client.get_user_activity('Millers') == []
        assert await client.get_user_journal('Millers', require_complete=True) == []
    finally:
        await client.close()
