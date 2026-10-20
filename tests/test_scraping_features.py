import pytest
from backloggd import Backloggd, BackloggdClient, CacheManager, UserProfile, UserSummary, JournalEntry, Review
from backloggd.models.game import GameEntry
from backloggd.parsers.profile import parse_user_profile_page
from backloggd.parsers.social import parse_user_social_page
from backloggd.parsers.journal import parse_journal_page
from backloggd.parsers.reviews import parse_game_reviews_page


MOCK_PROFILE_HTML = """
<html>
<body>
  <div class="avatar">
    <img src="https://backloggd-avatars.b-cdn.net/users/ardax12/avatar.jpg" />
  </div>
  <div id="profile-bio">
    JRPG and Souls enthusiast. Playing Elden Ring and Persona 5.
  </div>
  <button short_url="https://bckl.gg/XYZ123">Share</button>
  <div class="badges">
    <img src="/images/badges/goty-2025.svg" />
    <img src="/images/badges/replay-2024.svg" />
  </div>
  <div id="profile-favorites">
    <div class="game-cover" game_id="101">
      <a href="/games/chrono-trigger/">
        <img src="https://images.backloggd.com/chrono.jpg" alt="Chrono Trigger" />
      </a>
    </div>
    <div class="game-cover" game_id="102">
      <a href="/games/bloodborne/">
        <img src="https://images.backloggd.com/bb.jpg" alt="Bloodborne" />
      </a>
    </div>
  </div>
  <div class="profile-nav">
    <a href="/u/ardax12/games/">Games 350</a>
    <a href="/u/ardax12/games/playing/">Playing 4</a>
    <a href="/u/ardax12/games/backlog/">Backlog 120</a>
    <a href="/u/ardax12/games/wishlist/">Wishlist 45</a>
  </div>
</body>
</html>
"""

MOCK_SOCIAL_HTML = """
<html>
<body>
  <div class="card">
    <a href="/u/alice/">
      <img src="https://backloggd-avatars.b-cdn.net/users/alice/avatar.jpg" />
      <span>alice</span>
    </a>
  </div>
  <div class="card">
    <a href="/u/bob/">
      <img src="https://backloggd.com/no_avatar.jpg" />
      <span>bob</span>
    </a>
  </div>
  <a rel="next" href="/u/ardax12/following/?page=2">Next</a>
</body>
</html>
"""

MOCK_JOURNAL_HTML = """
<html>
<body>
  <h4>October 2026</h4>
  <h5>18</h5>
  <div class="row">
    <div class="game-cover" game_id="999">
      <img src="https://images.backloggd.com/metaphor.jpg" alt="Metaphor: ReFantazio" />
    </div>
    <div class="game-name">
      <a href="/games/metaphor-refantazio/">Metaphor: ReFantazio</a>
    </div>
    <div class="stars-top" style="width: 90%;"></div>
    <span class="replay">Replay</span>
  </div>
</body>
</html>
"""

MOCK_GAME_REVIEWS_HTML = """
<html>
<body>
  <h1>Metaphor: ReFantazio</h1>
  <div class="review-card">
    <a href="/u/critic1/">critic1</a>
    <a href="/u/critic1/review/555123/">View review</a>
    <div class="stars-top" style="width: 100%;"></div>
    <div class="review-text">An absolute masterpiece of modern JRPGs.</div>
    <span>42 Likes</span>
    <span>Oct 15, 2026</span>
  </div>
</body>
</html>
"""


def test_parse_user_profile_page():
    profile = parse_user_profile_page(MOCK_PROFILE_HTML, username="ardax12")
    assert profile.username == "ardax12"
    assert profile.avatar_url == "https://backloggd-avatars.b-cdn.net/users/ardax12/avatar.jpg"
    assert "JRPG and Souls enthusiast" in profile.bio
    assert profile.short_url == "https://bckl.gg/XYZ123"
    assert "goty_2025" in profile.badges
    assert len(profile.favorite_games) == 2
    assert profile.favorite_games[0].title == "Chrono Trigger"
    assert profile.favorite_games[0].slug == "chrono-trigger"
    assert profile.played_count == 350
    assert profile.playing_count == 4
    assert profile.backlog_count == 120
    assert profile.wishlist_count == 45


def test_profile_cache(tmp_path):
    db_file = tmp_path / "test_profile_cache.db"
    cache = CacheManager(cache_path=db_file, profile_ttl=3600.0)

    # Miss
    assert cache.get_profile("ardax12") is None

    # Set
    profile = UserProfile(
        username="ardax12",
        avatar_url="https://avatar.jpg",
        bio="Hello world",
        favorite_games=[GameEntry(slug="elden-ring", title="Elden Ring")],
        badges=["goty_2025"],
        played_count=100,
    )
    cache.set_profile(profile)

    # Hit
    cached = cache.get_profile("ardax12")
    assert cached is not None
    assert cached.username == "ardax12"
    assert cached.avatar_url == "https://avatar.jpg"
    assert cached.bio == "Hello world"
    assert len(cached.favorite_games) == 1
    assert cached.favorite_games[0].slug == "elden-ring"
    assert cached.badges == ["goty_2025"]
    assert cached.played_count == 100

    # Delete
    cache.delete_profile("ardax12")
    assert cache.get_profile("ardax12") is None


def test_parse_social_page():
    users, has_more = parse_user_social_page(MOCK_SOCIAL_HTML)
    assert len(users) == 2
    assert users[0].username == "alice"
    assert users[0].avatar_url == "https://backloggd-avatars.b-cdn.net/users/alice/avatar.jpg"
    assert users[1].username == "bob"
    assert users[1].avatar_url is None  # filtered out no_avatar.jpg
    assert has_more is True


def test_parse_journal_page():
    entries, has_more = parse_journal_page(MOCK_JOURNAL_HTML)
    assert len(entries) == 1
    e = entries[0]
    assert e.game_title == "Metaphor: ReFantazio"
    assert e.game_slug == "metaphor-refantazio"
    assert e.rating == 4.5
    assert e.is_replay is True
    assert "October 2026" in (e.played_date or "")
    assert has_more is False


def test_parse_game_reviews_page():
    reviews, has_more = parse_game_reviews_page(MOCK_GAME_REVIEWS_HTML, default_game_slug="metaphor-refantazio")
    assert len(reviews) == 1
    r = reviews[0]
    assert r.author == "critic1"
    assert r.review_id == "555123"
    assert r.rating == 5.0
    assert "masterpiece" in r.review_text
    assert r.like_count == 42


def test_sync_client_social_and_friends(monkeypatch):
    import httpx

    following_html = """
    <html><body>
      <div class="card"><a href="/u/user1/"><span>user1</span></a></div>
      <div class="card"><a href="/u/user2/"><span>user2</span></a></div>
    </body></html>
    """
    followers_html = """
    <html><body>
      <div class="card"><a href="/u/user2/"><span>user2</span></a></div>
      <div class="card"><a href="/u/user3/"><span>user3</span></a></div>
    </body></html>
    """

    def mock_get(self, method, url, **kwargs):
        req = httpx.Request(method, url)
        if "following" in str(url):
            return httpx.Response(200, text=following_html, request=req)
        elif "followers" in str(url):
            return httpx.Response(200, text=followers_html, request=req)
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_get)

    with Backloggd(cache_enabled=False) as client:
        following = client.get_user_following("testuser", max_pages=1)
        assert [u.username for u in following] == ["user1", "user2"]

        followers = client.get_user_followers("testuser", max_pages=1)
        assert [u.username for u in followers] == ["user2", "user3"]

        friends = client.get_user_friends("testuser")
        assert len(friends) == 1
        assert friends[0].username == "user2"


@pytest.mark.asyncio
async def test_async_client_profile_and_collections(monkeypatch, tmp_path):
    import httpx

    async def mock_send(self, request, *args, **kwargs):
        url = str(request.url)
        if url.endswith("/u/testuser/"):
            return httpx.Response(200, text=MOCK_PROFILE_HTML, request=request)
        elif "/games/playing/" in url:
            html = """<html><body><div class="col-cus-user-games"><div class="game-cover" game_id="1"><a href="/games/hollow-knight/"><img src="/hk.jpg" alt="Hollow Knight"/></a></div></div></body></html>"""
            return httpx.Response(200, text=html, request=request)
        elif "/journal/" in url:
            return httpx.Response(200, text=MOCK_JOURNAL_HTML, request=request)
        elif "/games/metaphor-refantazio/reviews" in url:
            return httpx.Response(200, text=MOCK_GAME_REVIEWS_HTML, request=request)
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", mock_send)

    cache_db = tmp_path / "async_test.db"
    async with BackloggdClient(cache_path=cache_db) as client:
        profile = await client.get_user_profile("testuser")
        assert profile.username == "testuser"
        assert profile.avatar_url is not None
        assert profile.short_url == "https://bckl.gg/XYZ123"

        # Targeted playing collection
        playing = await client.get_user_playing("testuser")
        assert len(playing) == 1
        assert playing[0].slug == "hollow-knight"

        # Journal
        journal = await client.get_user_journal("testuser")
        assert len(journal) == 1
        assert journal[0].game_slug == "metaphor-refantazio"

        # Game reviews
        reviews = await client.get_game_reviews("metaphor-refantazio")
        assert len(reviews) == 1
        assert reviews[0].author == "critic1"


def test_build_games_url():
    from backloggd.client import build_games_url

    # Base only
    assert build_games_url("https://backloggd.com/u/ardax12/games") == "https://backloggd.com/u/ardax12/games"

    # Sort only with alias
    assert build_games_url("https://backloggd.com/u/ardax12/games", sort="rating_desc") == "https://backloggd.com/u/ardax12/games/rating"
    assert build_games_url("https://backloggd.com/u/ardax12/games", sort="release_date") == "https://backloggd.com/u/ardax12/games/release"

    # String filter
    assert build_games_url("https://backloggd.com/u/ardax12/games", filter="type:played") == "https://backloggd.com/u/ardax12/games/type:played"

    # Dict filter with aliases and decimal conversion
    u = build_games_url(
        "https://backloggd.com/u/ardax12/games",
        sort="rating",
        filter={"type": "played", "platform": "win", "rating": 4.5},
    )
    assert u == "https://backloggd.com/u/ardax12/games/rating/type:played;release_platform:win;game_rating:4_5"


def test_sync_browse_games_and_library_sort(monkeypatch):
    import httpx

    catalog_html = """
    <html><body>
      <div class="col-cus-5"><div class="game-cover" game_id="10"><a href="/games/zelda-totk/"><img src="/zelda.jpg" alt="Zelda: Tears of the Kingdom"/></a></div></div>
    </body></html>
    """

    def mock_get(self, method, url, **kwargs):
        req = httpx.Request(method, url)
        return httpx.Response(200, text=catalog_html, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_get)

    with Backloggd(cache_enabled=False) as client:
        # 1. Browse games catalog
        catalog = client.browse_games(sort="popular", filter={"genre": "action"}, max_pages=1)
        assert len(catalog) == 1
        assert catalog[0].slug == "zelda-totk"

        # 2. Get user library with sort
        lib = client.get_user_library("testuser", sort="rating", filter={"type": "played"}, max_pages=1)
        assert len(lib) == 1
        assert lib["zelda-totk"].slug == "zelda-totk"

