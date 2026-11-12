from pathlib import Path

import httpx
import pytest

from backloggd import ActivitySnapshot, Backloggd, BackloggdClient, ChallengeResponseError, PageParseError


FIXTURES = Path(__file__).parent / "fixtures"
ACTIVITY = (FIXTURES / "millers_activity.html").read_text(encoding="utf-8")


def test_sync_snapshot_is_explicit_about_unsupported_history_and_keeps_list_api():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=ACTIVITY)

    client = Backloggd(cookies_file=None, cache_enabled=False)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        snapshot = client.get_user_activity_snapshot("Millers", max_pages=5)
        assert isinstance(snapshot, ActivitySnapshot)
        assert snapshot.coverage == "unsupported"
        assert snapshot.pages_read == 1
        assert len(snapshot.entries) == 1
        assert [request.url.params.get("page") for request in requests] == [None]

        latest = client.get_user_activity("Millers")
        assert latest == snapshot.entries
    finally:
        client.close()


def test_sync_snapshot_reports_a_boundary_found_on_the_latest_page():
    client = Backloggd(cookies_file=None, cache_enabled=False)
    client._client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=ACTIVITY)))
    try:
        event = client.get_user_activity("Millers")[0]
        snapshot = client.get_user_activity_snapshot("Millers", stop_at_ids=(event.activity_id,))
        assert snapshot.coverage == "boundary_reached"
        assert snapshot.pages_read == 1
        assert snapshot.entries[0].activity_id == event.activity_id
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_snapshot_matches_sync_contract():
    client = BackloggdClient(cookies_file=None, cache_enabled=False)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=ACTIVITY)))
    try:
        snapshot = await client.get_user_activity_snapshot("Millers", max_pages=5)
        assert isinstance(snapshot, ActivitySnapshot)
        assert snapshot.coverage == "unsupported"
        assert snapshot.pages_read == 1
        assert len(snapshot.entries) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_snapshot_does_not_turn_a_challenge_into_empty_history():
    client = BackloggdClient(cookies_file=None, cache_enabled=False)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<title>Making sure you're not a bot!</title>"))
    )
    try:
        with pytest.raises(ChallengeResponseError):
            await client.get_user_activity_snapshot("Millers")
    finally:
        await client.close()


def test_snapshot_keeps_valid_empty_activity_unconfirmed():
    client = Backloggd(cookies_file=None, cache_enabled=False)
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text='<div id="activities-list">No recent activity</div>'))
    )
    try:
        snapshot = client.get_user_activity_snapshot("Millers")
        assert snapshot.entries == []
        assert snapshot.coverage == "unsupported"
        assert snapshot.pages_read == 1
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_snapshot_rejects_an_unrecognized_layout():
    client = BackloggdClient(cookies_file=None, cache_enabled=False)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>unexpected markup</html>"))
    )
    try:
        with pytest.raises(PageParseError):
            await client.get_user_activity_snapshot("Millers")
    finally:
        await client.close()


@pytest.mark.parametrize("max_pages", [0, -1])
def test_snapshot_rejects_a_nonpositive_page_budget(max_pages):
    client = Backloggd(cookies_file=None, cache_enabled=False)
    try:
        with pytest.raises(ValueError, match="max_pages must be positive"):
            client.get_user_activity_snapshot("Millers", max_pages=max_pages)
    finally:
        client.close()
