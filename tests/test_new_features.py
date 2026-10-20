import tempfile
import time
from pathlib import Path
import pytest
from backloggd.cache import CacheManager
from backloggd.models.game import GameDetails, GameStatsSummary, GameEntry, GameStatus
from backloggd.models.review import Review
from backloggd.models.list import UserList, UserListSummary
from backloggd.parsers.game_page import parse_game_page
from backloggd.parsers.reviews import parse_user_reviews_page, parse_standalone_review_page
from backloggd.parsers.lists import parse_user_lists_overview, parse_single_list_page
from backloggd import Backloggd, BackloggdClient


def test_game_cache_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(cache_path=db_path, game_ttl=3600)

        # 1. Miss
        assert cache.get_game("hollow-knight") is None

        # 2. Add game
        game = GameDetails(
            slug="hollow-knight",
            title="Hollow Knight",
            release_year=2017,
            community_rating=4.5,
            summary="A challenging 2D metroidvania.",
            cover_url="https://images.igdb.com/test.jpg",
            game_id="12345",
            stats=GameStatsSummary(plays_count="85k", backlogs_count="20k", wishlists_count="15k"),
        )
        cache.set_game(game)

        # 3. Hit
        cached = cache.get_game("hollow-knight")
        assert cached is not None
        assert cached.title == "Hollow Knight"
        assert cached.release_year == 2017
        assert cached.community_rating == 4.5
        assert cached.stats.plays_count == "85k"

        # 4. Deletion
        cache.delete_game("hollow-knight")
        assert cache.get_game("hollow-knight") is None


def test_review_cache_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(cache_path=db_path, review_ttl=0.05)

        review = Review(
            review_id="998877",
            game_title="Celeste",
            game_slug="celeste",
            author="matt",
            rating=5.0,
            review_text="Absolute masterpiece of platforming and mental health themes.",
            like_count=42,
        )
        cache.set_review(review)

        cached = cache.get_review("998877")
        assert cached is not None
        assert cached.author == "matt"
        assert cached.like_count == 42

        # TTL expiration
        time.sleep(0.06)
        assert cache.get_review("998877") is None


def test_list_cache_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(cache_path=db_path, list_ttl=3600)

        list_url = "https://backloggd.com/u/ardax12/list/top-10-metroidvanias/"
        ulist = UserList(
            title="Top 10 Metroidvanias",
            slug="top-10-metroidvanias",
            author="ardax12",
            url=list_url,
            description="My all time favorites",
            games=[
                GameEntry(slug="super-metroid", title="Super Metroid", rating=5.0),
                GameEntry(slug="castlevania-sotn", title="Castlevania: Symphony of the Night", rating=4.5),
            ],
        )
        cache.set_list(ulist)

        cached = cache.get_list(list_url)
        assert cached is not None
        assert cached.title == "Top 10 Metroidvanias"
        assert len(cached.games) == 2
        assert cached.games[0].slug == "super-metroid"

        cache.delete_list(list_url)
        assert cache.get_list(list_url) is None


def test_parse_game_page_mock():
    html = """
    <html>
      <head><title>Hollow Knight (2017) - Backloggd</title></head>
      <body>
        <h1 id="game-title">Hollow Knight</h1>
        <h1>4.6</h1>
        <div class="game-description">Forge your own path in Hollow Knight! An epic action adventure through a vast ruined kingdom.</div>
        <div class="game-cover" game_id="11142">
          <img class="card-img" src="https://images.igdb.com/cover.jpg" />
        </div>
        <div class="stat-card">
          <h3>94k</h3>
          <h3>35k</h3>
          <h3>18k</h3>
        </div>
      </body>
    </html>
    """
    game = parse_game_page(html, slug="hollow-knight")
    assert game.slug == "hollow-knight"
    assert game.title == "Hollow Knight"
    assert game.release_year == 2017
    assert game.community_rating == 4.6
    assert "Forge your own path" in game.summary
    assert game.game_id == "11142"
    assert game.stats.plays_count == "94k"
    assert game.stats.backlogs_count == "35k"
    assert game.stats.wishlists_count == "18k"


def test_parse_reviews_mock():
    html = """
    <div class="user-reviews">
      <div class="game-name">
        <a href="/games/elden-ring/">Elden Ring</a>
      </div>
      <a href="/u/tarnished/review/554433/">Review Link</a>
      <div class="stars-top" style="width: 100%;"></div>
      <div class="review-text">Rise, Tarnished. Incredible open world game design.</div>
      <span class="like-counter">125 Likes</span>
    </div>
    """
    reviews, has_more = parse_user_reviews_page(html, author="tarnished")
    assert len(reviews) == 1
    rev = reviews[0]
    assert rev.game_title == "Elden Ring"
    assert rev.game_slug == "elden-ring"
    assert rev.review_id == "554433"
    assert rev.rating == 5.0
    assert "Rise, Tarnished" in rev.review_text
    assert rev.like_count == 125
    assert not has_more


def test_parse_lists_mock():
    overview_html = """
    <div class="lists-container">
      <a href="/u/gamer123/list/goty-2023/">GOTY 2023</a>
      <a href="/u/gamer123/list/backlog-priority/">Backlog Priority</a>
    </div>
    """
    summaries = parse_user_lists_overview(overview_html, author="gamer123")
    assert len(summaries) == 2
    assert summaries[0].title == "GOTY 2023"
    assert summaries[0].slug == "goty-2023"
    assert summaries[0].url == "https://backloggd.com/u/gamer123/list/goty-2023/"

    single_html = """
    <h1 id="list-title">GOTY 2023</h1>
    <div class="list-description">The best games released this year.</div>
    <div class="game-cover" game_id="999">
      <a href="/games/baldurs-gate-3/"><img alt="Baldur's Gate 3" src="/covers/bg3.jpg"/></a>
    </div>
    <div class="game-cover" game_id="888">
      <a href="/games/alan-wake-2/"><img alt="Alan Wake 2" src="/covers/aw2.jpg"/></a>
    </div>
    """
    user_list = parse_single_list_page(single_html, url="https://backloggd.com/u/gamer123/list/goty-2023/")
    assert user_list.title == "GOTY 2023"
    assert len(user_list.games) == 2
    assert user_list.games[0].title == "Baldur's Gate 3"
    assert user_list.games[0].slug == "baldurs-gate-3"
    assert user_list.games[1].title == "Alan Wake 2"


def test_sync_client_methods(monkeypatch):
    import httpx

    game_html = """
    <html>
      <head><title>Sekiro: Shadows Die Twice (2019) - Backloggd</title></head>
      <body>
        <h1 id="game-title">Sekiro: Shadows Die Twice</h1>
        <h1>4.8</h1>
        <div class="game-description">Carve your own clever path to vengeance.</div>
      </body>
    </html>
    """

    review_html = """
    <div class="user-reviews">
      <div class="game-name"><a href="/games/sekiro/">Sekiro</a></div>
      <a href="/u/ninja/review/112233/">Review</a>
      <div class="stars-top" style="width: 100%;"></div>
      <div class="review-text">Hesitation is defeat.</div>
      <span class="like-counter">50 Likes</span>
    </div>
    """

    standalone_review_html = """
    <html>
      <body>
        <a href="/games/sekiro/">Sekiro</a>
        <a href="/u/ninja/">ninja</a>
        <div class="stars-top" style="width: 100%;"></div>
        <div class="review-text">Hesitation is defeat. Perfect combat.</div>
      </body>
    </html>
    """

    def mock_request(self, method, url, *args, **kwargs):
        req = httpx.Request(method, url)
        if "/games/sekiro" in str(url):
            return httpx.Response(200, text=game_html, request=req)
        elif "/u/ninja/reviews/" in str(url):
            return httpx.Response(200, text=review_html, request=req)
        elif "/reviews/112233" in str(url):
            return httpx.Response(200, text=standalone_review_html, request=req)
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with Backloggd(cache_path=db_path) as client:
            # 1. get_game
            game = client.get_game("sekiro")
            assert game.title == "Sekiro: Shadows Die Twice"
            assert game.community_rating == 4.8
            # Verify it was cached
            cached_game = client.cache.get_game("sekiro")
            assert cached_game is not None
            assert cached_game.community_rating == 4.8

            # 2. get_user_reviews
            reviews = client.get_user_reviews("ninja")
            assert len(reviews) == 1
            assert reviews[0].game_slug == "sekiro"
            assert reviews[0].review_id == "112233"

            # 3. get_review
            rev = client.get_review("112233")
            assert rev.author == "ninja"
            assert "Hesitation is defeat" in rev.review_text


@pytest.mark.asyncio
async def test_async_client_methods(monkeypatch):
    import httpx

    game_html = """
    <html>
      <head><title>Portal 2 (2011) - Backloggd</title></head>
      <body>
        <h1 id="game-title">Portal 2</h1>
        <h1>4.9</h1>
      </body>
    </html>
    """

    async def mock_async_request(self, method, url, *args, **kwargs):
        req = httpx.Request(method, url)
        if "/games/portal-2" in str(url):
            return httpx.Response(200, text=game_html, request=req)
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_async_request)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_async.db"
        async with BackloggdClient(cache_path=db_path) as client:
            game = await client.get_game("portal-2")
            assert game.title == "Portal 2"
            assert game.community_rating == 4.9

            cached = client.cache.get_game("portal-2")
            assert cached is not None
            assert cached.title == "Portal 2"


def test_env_cookie_loading(monkeypatch):
    from backloggd.client import load_cookies

    # Test direct BACKLOGGD_SESSION env var
    monkeypatch.setenv("BACKLOGGD_SESSION", "my_secret_token_123")
    cookies = load_cookies(cookies_path="nonexistent_cookies.json")
    assert cookies.get("_backloggd_session") == "my_secret_token_123"


def test_granular_exceptions(monkeypatch):
    import httpx
    from backloggd.exceptions import (
        GameNotFoundError,
        UserNotFoundError,
        ListNotFoundError,
    )

    def mock_404(self, *args, **kwargs):
        req = httpx.Request("GET", "https://backloggd.com/notfound")
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_404)

    with Backloggd(cache_enabled=False) as client:
        with pytest.raises(GameNotFoundError):
            client.get_game("fake-game-slug-12345")

        with pytest.raises(UserNotFoundError):
            client.get_user_profile("fake-user-slug-12345")

        with pytest.raises(ListNotFoundError):
            client.get_list("https://backloggd.com/u/fake/list/fake/")


def test_search_games_parsing(monkeypatch):
    import httpx

    search_html = """
    <div class="row" game_id="14593">
      <div class="col-2">
        <a href="/games/hollow-knight/">
          <div class="game-cover" game_id="14593">
            <img alt="Hollow Knight" src="https://images.igdb.com/cover.jpg"/>
          </div>
        </a>
      </div>
      <div class="col">
        <div class="game-name">
          <a href="/games/hollow-knight/">
            <h3>Hollow Knight <span class="subtitle-text">2017</span></h3>
          </a>
        </div>
        <p class="game-details-value game-page-platform game-result-type">Main Game</p>
        <span class="game-detail">
          <p class="game-details-value game-page-platform">PC</p>
        </span>
        <span class="game-detail">
          <p class="game-details-value game-page-platform">Nintendo Switch</p>
        </span>
      </div>
    </div>
    """

    def mock_search(self, method, url, *args, **kwargs):
        req = httpx.Request(method, url)
        return httpx.Response(200, text=search_html, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_search)

    with Backloggd() as client:
        results = client.search_games("hollow knight")
        assert len(results) == 1
        res = results[0]
        assert res.title == "Hollow Knight"
        assert res.slug == "hollow-knight"
        assert res.release_year == 2017
        assert res.game_id == "14593"
        assert res.game_type == "Main Game"
        assert "PC" in res.platforms
        assert "Nintendo Switch" in res.platforms
        assert res.url == "https://backloggd.com/games/hollow-knight/"


def test_transient_retry_mechanism(monkeypatch):
    import httpx

    call_count = 0

    def mock_transient_failure(self, method, url, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request(method, url)
        if call_count == 1:
            # First attempt returns 502 Bad Gateway
            return httpx.Response(502, request=req)
        # Second attempt succeeds
        html = "<html><head><title>Test Game (2020)</title></head><body><h1>Test Game</h1></body></html>"
        return httpx.Response(200, text=html, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_transient_failure)

    with Backloggd(cache_enabled=False, max_retries=2) as client:
        game = client.get_game("test-game")
        assert game.title == "Test Game"
        assert call_count == 2


