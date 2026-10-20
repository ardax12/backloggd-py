# backloggd-py

[![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/project/backloggd-py/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests: 28 Passing](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)](#testing)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A modern, high-performance async & sync Python SDK, web scraper, and taste-matching recommendation engine for [Backloggd](https://backloggd.com).

Because Backloggd has no public REST API, `backloggd-py` provides an ergonomic, fully-typed interface to extract user libraries, profile cards, play journals, game reviews, and catalog queries—complete with an offline SQLite cache and Bayesian taste similarity analysis.

---

## Highlights

- **Dual Sync & Async Engines**: Use `Backloggd` for scripts, notebooks, and ETL, or `BackloggdClient` with `async`/`await` for Discord bots and FastAPI services.
- **Sub-Second Profile Scraping**: Direct `/u/<username>/` parser fetches avatars, bios, badges, pinned favorites, and quick counters in ~300ms without paginating thousands of library items.
- **Path-Based Sorting & Filtering**: Natural Python dictionaries that map cleanly to Backloggd's native URL path segments (`sort="rating"`, `filter={"genre": "rpg", "platform": "ps5"}`).
- **Targeted Collections**: Rapidly query active play statuses (`playing`, `backlog`, `wishlist`) without fetching entire backlogs.
- **Global Catalog Browsing**: Search any game or explore top games filtered by platform, genre, and release year.
- **Social Graph & Mutuals**: Extract followers and following lists, and automatically compute mutual friends.
- **Taste Recommendation Engine**: Bayesian Pearson correlation, Szymkiewicz-Simpson overlap, and Jaccard metrics to compare gaming tastes and recommend unplayed gems.
- **Transparent Multi-Table SQLite Cache**: Built-in TTL caching per entity (Profiles, Libraries, Games, Reviews, Lists) with instant invalidation.

---

## Quickstart

```python
from backloggd import Backloggd, GameStatus

with Backloggd() as client:
    # 1. Instant profile overview (~300ms)
    profile = client.get_user_profile("ardax12")
    print(f"{profile.username} | {profile.played_count} played | Bio: {profile.bio}")

    # 2. Paginated user library
    library = client.get_user_library("ardax12", max_pages=2)
    top_games = library.filter(status=GameStatus.PLAYED, min_rating=4.5)
    print(f"Top rated games ({len(top_games)}): {[g.title for g in top_games]}")

    # 3. Taste comparison between two users
    match = client.compare_users("ardax12", "nehir")
    print(f"Compatibility: {match.similarity_score}%")
    print("Mutual Favorites:", [g.title for g in match.mutual_favorites[:3]])
```

---

## Installation

### From Source (Current)

```bash
git clone https://github.com/ardax12/backloggd-matcher.git
cd backloggd-matcher
pip install -e .
```

Or using [`uv`](https://github.com/astral-sh/uv):
```bash
uv pip install -e ".[dev]"
```

### From PyPI (Upcoming v0.1.0 release)

```bash
pip install backloggd-py
```

---

## Authentication

Backloggd uses Cloudflare / Anubis bot verification. Providing your active session cookie bypasses challenge gates and unlocks full, unthrottled access.

### 1. Environment Variable (Recommended for CI / Docker / Cloud)

```bash
export BACKLOGGD_SESSION="your_cookie_value_here"
```

### 2. `cookies.json` File

Extract `_backloggd_session` from DevTools (`F12` -> Application -> Cookies -> `https://backloggd.com`) and save to `cookies.json`:

```json
[
  {
    "name": "_backloggd_session",
    "value": "your_cookie_value_here",
    "domain": "backloggd.com"
  }
]
```

*(A flat dictionary `{"_backloggd_session": "..."}` is also supported.)*

---

## Usage Guide

### 1. User Profiles (`get_user_profile`)

Fetches user metadata from the root profile page without scanning the game library:

```python
with Backloggd() as client:
    profile = client.get_user_profile("ardax12")

    print(profile.username)        # "ardax12"
    print(profile.avatar_url)      # "https://images.backloggd.com/..."
    print(profile.bio)             # User bio text
    print(profile.badges)          # ["goty_2025", "total_played3", ...]
    print(profile.short_url)       # "https://bckl.gg/..."
    print(profile.played_count)    # 248
    print(profile.playing_count)   # 3
    print(profile.backlog_count)   # 112
    print(profile.wishlist_count)  # 54

    # Pinned favorite games (list[GameEntry])
    for game in profile.favorite_games:
        print(f"★ {game.title} (Cover: {game.cover_url})")
```

### 2. User Libraries & Collections

```python
with Backloggd() as client:
    # Full library with pagination limit
    library = client.get_user_library("ardax12", max_pages=3)

    # Filter in-memory
    played_5_stars = library.filter(status="played", min_rating=5.0)

    # Export to CSV or Python dict
    library.to_csv("my_library.csv")
    records = library.to_dict()

    # Fast targeted queries (bypasses full library pagination)
    playing = client.get_user_playing("ardax12")
    backlog = client.get_user_backlog("ardax12", max_pages=1)
    wishlist = client.get_user_wishlist("ardax12", max_pages=1)
```

### 3. Path-Based Sorting & Filtering

Backloggd organizes filters as URL path segments (e.g. `/games/rating/type:played;release_platform:ps5/`). The SDK translates standard Python dictionaries:

```python
with Backloggd() as client:
    # Supported sort keys: "popular", "rating", "release", "title", "last_played", "played"
    top_ps5_played = client.get_user_library(
        "ardax12",
        sort="rating",
        filter={"type": "played", "platform": "ps5"},
        max_pages=2,
    )

    # Sort targeted collections
    wishlist_by_popularity = client.get_user_wishlist("ardax12", sort="popular")
```

### 4. Global Games Catalog Browsing

Explore or search games across Backloggd:

```python
with Backloggd() as client:
    # Search for a specific title
    results = client.search_games("Metaphor ReFantazio")
    for r in results:
        print(f"{r.title} ({r.release_year}) -> {r.slug}")

    # Browse catalog with sorting & category filtering
    popular_rpgs = client.browse_games(
        sort="popular",
        filter={"genre": "role-playing-rpg", "platform": "win"},
        max_pages=1,
    )

    # Game details
    elden_ring = client.get_game("elden-ring")
    print(f"{elden_ring.title}: {elden_ring.rating_stars}* ({elden_ring.plays_count} plays)")
```

### 5. Social Graph: Followers, Following & Friends

```python
with Backloggd() as client:
    following = client.get_user_following("ardax12", max_pages=1)
    followers = client.get_user_followers("ardax12", max_pages=1)

    # Automatically compute mutual friends (followers ∩ following)
    friends = client.get_user_friends("ardax12")
    for friend in friends:
        print(f"Mutual friend: {friend.username} ({friend.url})")
```

### 6. Play Journal & Community Reviews

```python
with Backloggd() as client:
    # Completion journal
    journal = client.get_user_journal("ardax12", max_pages=1)
    for entry in journal:
        replay = " [Replay]" if entry.is_replay else ""
        print(f"{entry.played_date}: {entry.game_title} - {entry.rating}*{replay}")

    # Game reviews
    reviews = client.get_game_reviews("hollow-knight", max_pages=1)
    for rev in reviews[:3]:
        print(f"{rev.author} ({rev.rating}*): {rev.review_text[:100]}...")
```

### 7. Taste Matching & Recommendations

Computes taste compatibility using normalized Bayesian Pearson correlation, Jaccard overlap, and relative rating agreement:

```python
with Backloggd() as client:
    match = client.compare_users("ardax12", "nehir", max_pages=2)

    print(f"Match Score: {match.similarity_score}%")
    print(f"Shared Games: {match.overlap_count}")

    print("Mutual Favorites:")
    for g in match.mutual_favorites:
        print(f" - {g.title}")

    print("Polarizing Disagreements:")
    for d in match.disagreements:
        print(f" - {d.title}: {d.user1_rating}* vs {d.user2_rating}*")

    print("Recommendations for User 1:")
    for rec in match.recommendations_for_user1[:5]:
        print(f" - {rec.title}")
```

### 8. Asynchronous Client (`BackloggdClient`)

For high-throughput bots, crawlers, or asynchronous web frameworks:

```python
import asyncio
from backloggd import BackloggdClient

async def main():
    async with BackloggdClient(cookies_file="cookies.json") as client:
        # Run requests concurrently
        profile, playing, catalog = await asyncio.gather(
            client.get_user_profile("ardax12"),
            client.get_user_playing("ardax12"),
            client.browse_games(sort="popular", max_pages=1),
        )
        print(f"Profile: {profile.username}")
        print(f"Currently playing: {len(playing)} games")
        print(f"Top game: {catalog[0].title}")

asyncio.run(main())
```

### 9. SQLite Caching & Invalidation

All responses are cached locally in SQLite (`.cache/backloggd_cache.db`) with granular TTLs:

| Entity | SQLite Table | Default TTL |
|:---|:---|:---|
| User Profile | `profile_cache` | 24 Hours (`86400s`) |
| User Library | `library_cache` | 24 Hours (`86400s`) |
| Game Details | `game_cache` | 7 Days (`604800s`) |
| Game Reviews | `review_cache` | 24 Hours (`86400s`) |
| Custom Lists | `list_cache` | 24 Hours (`86400s`) |

```python
# Custom TTL configuration
client = Backloggd(
    profile_ttl=3600.0,       # 1 hour
    library_ttl=3600.0,       # 1 hour
    game_ttl=86400.0 * 14,    # 14 days
    cache_path="data/custom_cache.db",
)

# Invalidation helpers
client.cache.delete_profile("ardax12")
client.cache.delete_library("ardax12")
client.cache.delete_game("elden-ring")
client.cache.clear()  # Flush entire database
```

### 10. Error Handling

```python
from backloggd import Backloggd
from backloggd.exceptions import (
    BackloggdError,
    ChallengeResponseError,
    RateLimitError,
    UserNotFoundError,
    GameNotFoundError,
)

with Backloggd() as client:
    try:
        game = client.get_game("unknown-slug-xyz")
    except GameNotFoundError:
        print("Game not found on Backloggd.")
    except ChallengeResponseError:
        print("Cloudflare anti-bot challenge encountered. Update your session cookie.")
    except RateLimitError:
        print("HTTP 429 Rate limited. Automatic backoff failed.")
    except BackloggdError as e:
        print(f"SDK error: {e}")
```

---

## API Parity Matrix

Both sync and async clients share identical capabilities and signatures:

| Capability | Synchronous (`Backloggd`) | Asynchronous (`BackloggdClient`) |
|:---|:---|:---|
| Profile Lookup | `get_user_profile(user)` | `await get_user_profile(user)` |
| Full Library | `get_user_library(user, ...)` | `await get_user_library(user, ...)` |
| Targeted Collections | `get_user_playing()`, `get_user_backlog()`, `get_user_wishlist()` | `await get_user_playing()`, `get_user_backlog()`, `get_user_wishlist()` |
| Browse Catalog | `browse_games(sort=..., filter=...)` | `await browse_games(sort=..., filter=...)` |
| Search Games | `search_games(query)` | `await search_games(query)` |
| Game Details | `get_game(slug)` | `await get_game(slug)` |
| Game Reviews | `get_game_reviews(slug)` | `await get_game_reviews(slug)` |
| User Reviews | `get_user_reviews(user)` | `await get_user_reviews(user)` |
| User Lists | `get_user_lists(user)`, `get_list(url)` | `await get_user_lists(user)`, `get_list(url)` |
| Social Graph | `get_user_followers()`, `get_user_following()`, `get_user_friends()` | `await get_user_followers()`, `get_user_following()`, `get_user_friends()` |
| Play Journal | `get_user_journal(user)` | `await get_user_journal(user)` |
| Taste Matching | `compare_users(user1, user2)` | `await compare_users(user1, user2)` |

---

## Testing

Run the full test suite with 28 unit and integration tests:

```bash
# Using pytest
pytest

# Or via uv
uv run pytest
```

---

## Roadmap

- [x] Dual sync & async client architecture with 100% method parity
- [x] Sub-second profile scraping (`get_user_profile`)
- [x] Full paginated library retrieval with bounded concurrency
- [x] Path-based URL sorting and multi-criteria filtering
- [x] Targeted instant collections (`playing`, `backlog`, `wishlist`)
- [x] Social network scraping and mutual friends calculation
- [x] Playthrough journal & community review extraction
- [x] Global games catalog browsing (`browse_games`)
- [x] Persistent multi-table SQLite cache with customizable TTLs
- [x] Bayesian taste similarity engine & recommendations
- [ ] Rich terminal CLI (`backloggd-cli`)
- [ ] PyPI publishing via GitHub Actions CI/CD

---

## License

Distributed under the [MIT License](LICENSE).
