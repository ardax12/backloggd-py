"""SQLite-based persistent cache layer for Backloggd entities (Users, Games, Reviews, Lists)."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional, Union
from backloggd.models.game import GameEntry, GameStatus, GameDetails, GameStatsSummary
from backloggd.models.library import UserLibrary
from backloggd.models.user import UserProfile
from backloggd.models.review import Review
from backloggd.models.list import UserList

DEFAULT_CACHE_DIR = Path(".cache")
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "backloggd_cache.db"
DEFAULT_LIBRARY_TTL = 86400.0       # 24 hours
DEFAULT_PROFILE_TTL = 86400.0       # 24 hours
DEFAULT_GAME_TTL = 604800.0         # 7 days
DEFAULT_REVIEW_TTL = 86400.0        # 24 hours
DEFAULT_LIST_TTL = 86400.0          # 24 hours


class CacheManager:
    """Manages SQLite cache for user profiles, libraries, games, reviews, and lists with TTL expiration."""

    def __init__(
        self,
        cache_path: Optional[Union[str, Path]] = None,
        library_ttl: float = DEFAULT_LIBRARY_TTL,
        profile_ttl: float = DEFAULT_PROFILE_TTL,
        game_ttl: float = DEFAULT_GAME_TTL,
        review_ttl: float = DEFAULT_REVIEW_TTL,
        list_ttl: float = DEFAULT_LIST_TTL,
        ttl_seconds: Optional[float] = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.library_ttl = ttl_seconds if ttl_seconds is not None else library_ttl
        self.profile_ttl = profile_ttl
        self.game_ttl = game_ttl
        self.review_ttl = review_ttl
        self.list_ttl = list_ttl
        self.cache_path = Path(cache_path) if cache_path else DEFAULT_CACHE_FILE

        if self.enabled:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema with all entity tables."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_cache (
                    username TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_cache (
                    username TEXT PRIMARY KEY,
                    library_json TEXT NOT NULL,
                    total_games INTEGER NOT NULL,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS game_cache (
                    slug TEXT PRIMARY KEY,
                    game_json TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_cache (
                    review_id TEXT PRIMARY KEY,
                    review_json TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS list_cache (
                    list_url TEXT PRIMARY KEY,
                    list_json TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ==================== User Profile Cache ====================

    def get_profile(self, username: str, max_age: Optional[float] = None) -> Optional[UserProfile]:
        """Retrieve a cached UserProfile if present and unexpired."""
        if not self.enabled:
            return None

        clean_user = username.lower().strip()
        ttl = max_age if max_age is not None else self.profile_ttl

        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute(
                "SELECT profile_json, cached_at FROM profile_cache WHERE username = ?",
                (clean_user,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            profile_json, cached_at = row
            if ttl is not None and (time.time() - cached_at) >= ttl:
                return None

            d = json.loads(profile_json)
            fav_games = [
                GameEntry(
                    slug=g["slug"],
                    title=g["title"],
                    cover_url=g.get("cover_url"),
                    game_id=g.get("game_id"),
                )
                for g in d.get("favorite_games", [])
            ]
            return UserProfile(
                username=d["username"],
                avatar_url=d.get("avatar_url"),
                bio=d.get("bio"),
                favorite_games=fav_games,
                badges=d.get("badges", []),
                short_url=d.get("short_url"),
                played_count=d.get("played_count"),
                playing_count=d.get("playing_count"),
                backlog_count=d.get("backlog_count"),
                wishlist_count=d.get("wishlist_count"),
            )
        except Exception:
            return None
        finally:
            conn.close()

    def set_profile(self, profile: UserProfile) -> None:
        """Store a UserProfile in the cache."""
        if not self.enabled or not profile:
            return

        clean_user = profile.username.lower().strip()
        data = {
            "username": profile.username,
            "avatar_url": profile.avatar_url,
            "bio": profile.bio,
            "favorite_games": [
                {
                    "slug": g.slug,
                    "title": g.title,
                    "cover_url": g.cover_url,
                    "game_id": g.game_id,
                }
                for g in profile.favorite_games
            ],
            "badges": profile.badges,
            "short_url": profile.short_url,
            "played_count": profile.played_count,
            "playing_count": profile.playing_count,
            "backlog_count": profile.backlog_count,
            "wishlist_count": profile.wishlist_count,
        }

        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                INSERT INTO profile_cache (username, profile_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    cached_at = excluded.cached_at
                """,
                (clean_user, json.dumps(data), time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def delete_profile(self, username: str) -> None:
        """Invalidate profile cache for a specific user."""
        if not self.enabled:
            return
        clean_user = username.lower().strip()
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM profile_cache WHERE username = ?", (clean_user,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # ==================== User Library Cache ====================

    def get_library(self, username: str, max_age: Optional[float] = None) -> Optional[UserLibrary]:
        """Retrieve a cached UserLibrary if present and unexpired."""
        if not self.enabled:
            return None

        clean_user = username.lower().strip()
        ttl = max_age if max_age is not None else self.library_ttl

        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute(
                "SELECT library_json, cached_at FROM library_cache WHERE username = ?",
                (clean_user,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            library_json, cached_at = row
            if ttl is not None and (time.time() - cached_at) >= ttl:
                return None

            data = json.loads(library_json) if isinstance(library_json, str) else library_json
            library = UserLibrary(username=clean_user)
            for item in data:
                library.add(
                    GameEntry(
                        slug=item["slug"],
                        title=item["title"],
                        rating=item.get("rating"),
                        status=GameStatus(item.get("status", "unknown")),
                        status_title=item.get("status_title"),
                        is_liked=item.get("is_liked", False),
                        cover_url=item.get("cover_url"),
                        game_id=item.get("game_id"),
                        log_id=item.get("log_id"),
                    )
                )
            return library
        except Exception:
            return None
        finally:
            conn.close()

    # Convenience aliases
    get = get_library
    get_user = get_library

    def set_library(self, library: UserLibrary) -> None:
        """Store a UserLibrary in the cache."""
        if not self.enabled or not library:
            return

        clean_user = library.username.lower().strip()
        data = [
            {
                "slug": g.slug,
                "title": g.title,
                "rating": g.rating,
                "status": g.status.value,
                "status_title": g.status_title,
                "is_liked": g.is_liked,
                "cover_url": g.cover_url,
                "game_id": g.game_id,
                "log_id": g.log_id,
            }
            for g in library
        ]

        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                INSERT INTO library_cache (username, library_json, total_games, cached_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    library_json = excluded.library_json,
                    total_games = excluded.total_games,
                    cached_at = excluded.cached_at
                """,
                (clean_user, json.dumps(data), len(library), time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # Convenience aliases
    set = set_library
    set_user = set_library

    def delete_library(self, username: str) -> None:
        """Invalidate library cache for a specific user."""
        if not self.enabled:
            return
        clean_user = username.lower().strip()
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM library_cache WHERE username = ?", (clean_user,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # Convenience aliases
    delete = delete_library
    delete_user = delete_library


    # ==================== Game Details Cache ====================

    def get_game(self, slug: str, max_age: Optional[float] = None) -> Optional[GameDetails]:
        """Retrieve cached GameDetails."""
        if not self.enabled:
            return None

        clean_slug = slug.lower().strip()
        ttl = max_age if max_age is not None else self.game_ttl

        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute("SELECT game_json, cached_at FROM game_cache WHERE slug = ?", (clean_slug,))
            row = cursor.fetchone()
            if not row:
                return None

            game_json, cached_at = row
            if ttl is not None and (time.time() - cached_at) >= ttl:
                return None

            d = json.loads(game_json)
            stats_dict = d.get("stats", {})
            return GameDetails(
                slug=d["slug"],
                title=d["title"],
                release_year=d.get("release_year"),
                community_rating=d.get("community_rating"),
                summary=d.get("summary"),
                cover_url=d.get("cover_url"),
                game_id=d.get("game_id"),
                stats=GameStatsSummary(
                    plays_count=stats_dict.get("plays_count"),
                    backlogs_count=stats_dict.get("backlogs_count"),
                    wishlists_count=stats_dict.get("wishlists_count"),
                ),
            )
        except Exception:
            return None
        finally:
            conn.close()

    def set_game(self, game: GameDetails) -> None:
        """Store GameDetails in the cache."""
        if not self.enabled or not game:
            return

        data = {
            "slug": game.slug,
            "title": game.title,
            "release_year": game.release_year,
            "community_rating": game.community_rating,
            "summary": game.summary,
            "cover_url": game.cover_url,
            "game_id": game.game_id,
            "stats": {
                "plays_count": game.stats.plays_count,
                "backlogs_count": game.stats.backlogs_count,
                "wishlists_count": game.stats.wishlists_count,
            },
        }

        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                INSERT INTO game_cache (slug, game_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    game_json = excluded.game_json,
                    cached_at = excluded.cached_at
                """,
                (game.slug.lower(), json.dumps(data), time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def delete_game(self, slug: str) -> None:
        """Invalidate cache for a specific game."""
        if not self.enabled:
            return
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM game_cache WHERE slug = ?", (slug.lower(),))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # ==================== Review Cache ====================

    def get_review(self, review_id: str, max_age: Optional[float] = None) -> Optional[Review]:
        """Retrieve a review by review_id."""
        if not self.enabled:
            return None

        clean_id = str(review_id).strip()
        ttl = max_age if max_age is not None else self.review_ttl

        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute("SELECT review_json, cached_at FROM review_cache WHERE review_id = ?", (clean_id,))
            row = cursor.fetchone()
            if not row:
                return None

            review_json, cached_at = row
            if ttl is not None and (time.time() - cached_at) >= ttl:
                return None

            d = json.loads(review_json)
            return Review(
                review_id=d["review_id"],
                game_title=d["game_title"],
                game_slug=d["game_slug"],
                author=d["author"],
                rating=d.get("rating"),
                review_text=d.get("review_text", ""),
                created_at=d.get("created_at"),
                like_count=d.get("like_count", 0),
                has_spoilers=d.get("has_spoilers", False),
            )
        except Exception:
            return None
        finally:
            conn.close()

    def set_review(self, review: Review) -> None:
        """Store a Review in the cache."""
        if not self.enabled or not review or not review.review_id:
            return

        data = {
            "review_id": review.review_id,
            "game_title": review.game_title,
            "game_slug": review.game_slug,
            "author": review.author,
            "rating": review.rating,
            "review_text": review.review_text,
            "created_at": review.created_at,
            "like_count": review.like_count,
            "has_spoilers": review.has_spoilers,
        }

        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                INSERT INTO review_cache (review_id, review_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(review_id) DO UPDATE SET
                    review_json = excluded.review_json,
                    cached_at = excluded.cached_at
                """,
                (str(review.review_id), json.dumps(data), time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def delete_review(self, review_id: str) -> None:
        """Invalidate cache for a specific review."""
        if not self.enabled:
            return
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM review_cache WHERE review_id = ?", (str(review_id),))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # ==================== User List Cache ====================

    def get_list(self, list_url: str, max_age: Optional[float] = None) -> Optional[UserList]:
        """Retrieve a cached UserList by URL."""
        if not self.enabled:
            return None

        clean_url = list_url.strip()
        ttl = max_age if max_age is not None else self.list_ttl

        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute("SELECT list_json, cached_at FROM list_cache WHERE list_url = ?", (clean_url,))
            row = cursor.fetchone()
            if not row:
                return None

            list_json, cached_at = row
            if ttl is not None and (time.time() - cached_at) >= ttl:
                return None

            d = json.loads(list_json)
            games = [
                GameEntry(
                    slug=g["slug"],
                    title=g["title"],
                    rating=g.get("rating"),
                    cover_url=g.get("cover_url"),
                    game_id=g.get("game_id"),
                )
                for g in d.get("games", [])
            ]
            return UserList(
                title=d["title"],
                slug=d["slug"],
                author=d["author"],
                url=d["url"],
                description=d.get("description"),
                games=games,
            )
        except Exception:
            return None
        finally:
            conn.close()

    def set_list(self, user_list: UserList) -> None:
        """Store a UserList in the cache."""
        if not self.enabled or not user_list:
            return

        data = {
            "title": user_list.title,
            "slug": user_list.slug,
            "author": user_list.author,
            "url": user_list.url,
            "description": user_list.description,
            "games": [
                {
                    "slug": g.slug,
                    "title": g.title,
                    "rating": g.rating,
                    "cover_url": g.cover_url,
                    "game_id": g.game_id,
                }
                for g in user_list.games
            ],
        }

        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute(
                """
                INSERT INTO list_cache (list_url, list_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(list_url) DO UPDATE SET
                    list_json = excluded.list_json,
                    cached_at = excluded.cached_at
                """,
                (user_list.url, json.dumps(data), time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def delete_list(self, list_url: str) -> None:
        """Invalidate cache for a specific list."""
        if not self.enabled:
            return
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM list_cache WHERE list_url = ?", (list_url.strip(),))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # ==================== Global Cache Flush ====================

    def clear(self) -> None:
        """Clear the entire cache database."""
        if not self.enabled:
            return
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM profile_cache")
            conn.execute("DELETE FROM library_cache")
            conn.execute("DELETE FROM game_cache")
            conn.execute("DELETE FROM review_cache")
            conn.execute("DELETE FROM list_cache")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
