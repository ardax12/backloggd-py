import json
import sqlite3
import time
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from backloggd import Backloggd, BackloggdClient, CacheManager, GameStatus
from backloggd.parsers.games import parse_games_page


FIXTURES = Path(__file__).parent / "fixtures"


def html(name):
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("name,status,count", [
    ("millers_games_played", GameStatus.PLAYED, 70),
    ("millers_games_played_page2", GameStatus.PLAYED, 70),
    ("barryquill_games_playing", GameStatus.PLAYING, 3),
    ("barryquill_games_wishlist", GameStatus.WISHLIST, 2),
])
def test_real_collections_use_owner_status_not_viewer_quick_edit(name, status, count):
    games, _ = parse_games_page(html(name))
    assert len(games) == count
    assert {game.status for game in games} == {status}
    assert all(game.log_id is None and game.logged_at is None for game in games)
    assert all(game.status_title is None and not game.is_liked for game in games)


def test_actual_playing_page_conflicts_with_viewers_completed_games():
    games, _ = parse_games_page(html("barryquill_games_playing"))
    gta = next(game for game in games if game.slug == "grand-theft-auto-iv")
    assert gta.status == GameStatus.PLAYING
    assert gta.rating == 5.0  # Owner rating 10; the viewer's preloaded rating is 8.
    assert gta.status_title is None  # Viewer says Completed; no owner completion evidence.
    assert gta.log_id is None  # Viewer log 12271173 must not be attributed to barryquill.


def test_removing_viewer_metadata_does_not_change_owner_results():
    original = html("millers_games_played")
    soup = BeautifulSoup(original, "html.parser")
    for tag in soup.select('[id^="preloaded-log-"]'):
        tag.decompose()
    for cover in soup.select(".game-cover"):
        cover["class"] = [value for value in cover.get("class", []) if not value.startswith("fade-")]
    before, _ = parse_games_page(original)
    after, _ = parse_games_page(str(soup))
    assert before == after


def test_actual_unrated_owner_game_does_not_inherit_viewer_rating():
    games, _ = parse_games_page(html("millers_games_played"))
    overwatch = next(game for game in games if game.slug == "overwatch")
    assert overwatch.status == GameStatus.PLAYED
    assert overwatch.rating is None  # Viewer's hidden rating is 5 (2.5 stars).


def test_cards_without_owner_collection_evidence_do_not_use_viewer_status():
    soup = BeautifulSoup(html("barryquill_games_playing"), "html.parser")
    soup.select_one('[data-controller~="game-filters"]').decompose()
    games, _ = parse_games_page(str(soup))
    assert len(games) == 3
    assert {game.status for game in games} == {GameStatus.UNKNOWN}


def test_conflicting_owner_collection_markers_are_unknown():
    soup = BeautifulSoup(html("barryquill_games_playing"), "html.parser")
    marker = soup.select_one('[data-controller~="game-filters"]')
    marker["data-game-filters-preset-value"] = "wishlist"
    games, _ = parse_games_page(str(soup))
    assert {game.status for game in games} == {GameStatus.UNKNOWN}


@pytest.mark.parametrize("collection", ["playing", "backlog", "wishlist"])
def test_real_empty_collections_stay_empty(collection):
    games, has_more = parse_games_page(html(f"millers_games_{collection}"))
    assert games == []
    assert not has_more


def transport_handler(request):
    if request.url.path == "/u/Millers/games":
        suffix = "_page2" if request.url.params.get("page") == "2" else ""
        return httpx.Response(200, text=html(f"millers_games_played{suffix}"))
    if request.url.path == "/u/barryquill/games/playing/":
        return httpx.Response(200, text=html("barryquill_games_playing"))
    if request.url.path == "/u/barryquill/games/wishlist/":
        return httpx.Response(200, text=html("barryquill_games_wishlist"))
    if request.url.path == "/u/Millers/games/backlog/":
        return httpx.Response(200, text=html("millers_games_backlog"))
    raise AssertionError(f"Unexpected request {request.url.path}")


def assert_library(library):
    assert len(library) == 140
    assert {game.status for game in library} == {GameStatus.PLAYED}
    assert library["grand-theft-auto-vice-city"].rating == 3.0


def test_sync_public_apis_preserve_owner_status_across_pages_and_collections():
    client = Backloggd(cookies_file=None, cache_enabled=False, request_delay=0, max_concurrency=1)
    client._client = httpx.Client(transport=httpx.MockTransport(transport_handler))
    try:
        assert_library(client.get_user_library("Millers", max_pages=2))
        assert {game.status for game in client.get_user_playing("barryquill")} == {GameStatus.PLAYING}
        assert {game.status for game in client.get_user_wishlist("barryquill")} == {GameStatus.WISHLIST}
        assert client.get_user_backlog("Millers") == []
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_public_apis_preserve_owner_status_across_pages_and_collections():
    client = BackloggdClient(cookies_file=None, cache_enabled=False, request_delay=0, max_concurrency=1)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    try:
        assert_library(await client.get_user_library("Millers", max_pages=2))
        assert {game.status for game in await client.get_user_playing("barryquill")} == {GameStatus.PLAYING}
        assert {game.status for game in await client.get_user_wishlist("barryquill")} == {GameStatus.WISHLIST}
        assert await client.get_user_backlog("Millers") == []
    finally:
        await client.close()


def test_legacy_library_cache_with_viewer_statuses_is_not_reused(tmp_path):
    cache = CacheManager(cache_path=tmp_path / "cache.db")
    with sqlite3.connect(cache.cache_path) as connection:
        connection.execute(
            "INSERT INTO library_cache VALUES (?, ?, ?, ?)",
            ("barryquill", json.dumps([{
                "slug": "grand-theft-auto-iv", "title": "Grand Theft Auto IV",
                "status": "played", "log_id": "12271173", "status_title": "Completed",
            }]), 1, time.time()),
        )
    assert cache.get_library("barryquill") is None
