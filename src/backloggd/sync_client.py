"""Synchronous Backloggd client with HTTP/2, ThreadPool concurrency, and SQLite caching."""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Union, Callable
import httpx

from backloggd.exceptions import (
    BackloggdError,
    ChallengeResponseError,
    RateLimitError,
    ResourceNotFoundError,
    UserNotFoundError,
    GameNotFoundError,
    ListNotFoundError,
    ReviewNotFoundError,
)
from backloggd.models.game import GameEntry, GameDetails, GameStatsSummary, GameSearchResult
from backloggd.models.library import UserLibrary
from backloggd.models.user import UserProfile, UserSummary
from backloggd.models.journal import JournalEntry
from backloggd.models.comparison import MatchComparison
from backloggd.models.review import Review
from backloggd.models.list import UserList, UserListSummary
from backloggd.parsers.games import parse_games_page
from backloggd.parsers.game_page import parse_game_page
from backloggd.parsers.reviews import (
    parse_user_reviews_page,
    parse_standalone_review_page,
    parse_game_reviews_page,
)
from backloggd.parsers.lists import parse_user_lists_overview, parse_single_list_page
from backloggd.parsers.search import parse_game_search_results
from backloggd.parsers.profile import parse_user_profile_page
from backloggd.parsers.social import parse_user_social_page
from backloggd.parsers.journal import parse_journal_page
from backloggd.analytics.matcher import compare_libraries
from backloggd.cache import (
    CacheManager,
    DEFAULT_LIBRARY_TTL,
    DEFAULT_PROFILE_TTL,
    DEFAULT_GAME_TTL,
    DEFAULT_REVIEW_TTL,
    DEFAULT_LIST_TTL,
)
from backloggd.utils import (
    BASE_URL,
    DEFAULT_COOKIES_FILE,
    DEFAULT_HEADERS,
    load_cookies,
    build_games_url,
    clean_username,
    clean_slug,
)

logger = logging.getLogger("backloggd")


class Backloggd:
    """Synchronous Backloggd client with HTTP/2 and SQLite caching.

    Ideal for fast scripts, REPLs, Jupyter notebooks, or when you don't want
    to manage `asyncio.run()` or `async/await`.

    Example:
        >>> from backloggd import Backloggd
        >>> client = Backloggd()
        >>> profile = client.get_user_profile("ardax12")
        >>> print(profile.username, profile.avatar_url)
    """

    def __init__(
        self,
        cookies: Optional[dict[str, str]] = None,
        cookies_file: Optional[Union[str, Path]] = DEFAULT_COOKIES_FILE,
        timeout: float = 20.0,
        request_delay: float = 0.05,
        max_concurrency: int = 4,
        max_retries: int = 2,
        cache_enabled: bool = True,
        cache_ttl: Optional[float] = None,
        library_ttl: float = DEFAULT_LIBRARY_TTL,
        profile_ttl: float = DEFAULT_PROFILE_TTL,
        game_ttl: float = DEFAULT_GAME_TTL,
        review_ttl: float = DEFAULT_REVIEW_TTL,
        list_ttl: float = DEFAULT_LIST_TTL,
        cache_path: Optional[Union[str, Path]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.timeout = timeout
        self.request_delay = request_delay
        self.max_concurrency = max(1, max_concurrency)
        self.max_retries = max(0, max_retries)

        merged_cookies = load_cookies(cookies_file) if cookies_file else {}
        if cookies:
            merged_cookies.update(cookies)
        self.cookies = merged_cookies

        req_headers = dict(DEFAULT_HEADERS)
        if headers:
            req_headers.update(headers)
        self.headers = req_headers

        self._client: Optional[httpx.Client] = None
        self.cache = CacheManager(
            cache_path=cache_path,
            library_ttl=cache_ttl if cache_ttl is not None else library_ttl,
            profile_ttl=profile_ttl,
            game_ttl=game_ttl,
            review_ttl=review_ttl,
            list_ttl=list_ttl,
            enabled=cache_enabled,
        )

    def __enter__(self) -> "Backloggd":
        self._get_client()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self.headers,
                cookies=self.cookies if self.cookies else None,
                timeout=self.timeout,
                http2=True,
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def _check_response(self, resp: httpx.Response, resource_type: str = "resource") -> None:
        """Verify response is valid and not an anti-bot challenge or block."""
        body = resp.text[:200_000].lower()
        challenge_markers = (
            "anubis",
            "proof-of-work",
            "proof of work",
            "anubis_challenge",
            "making sure you're not a bot",
            "making sure you are not a bot",
        )
        if any(marker in body for marker in challenge_markers):
            raise ChallengeResponseError(
                f"Backloggd returned an anti-bot challenge (HTTP {resp.status_code}) for {resp.url}. "
                "Ensure you pass a valid session cookie in cookies.json or BACKLOGGD_SESSION env var."
            )

        if resp.status_code == 404:
            if resource_type == "user":
                raise UserNotFoundError(f"User profile not found (HTTP 404): {resp.url}")
            elif resource_type == "game":
                raise GameNotFoundError(f"Game not found (HTTP 404): {resp.url}")
            elif resource_type == "list":
                raise ListNotFoundError(f"List not found (HTTP 404): {resp.url}")
            elif resource_type == "review":
                raise ReviewNotFoundError(f"Review not found (HTTP 404): {resp.url}")
            raise ResourceNotFoundError(f"Requested resource not found (HTTP 404): {resp.url}")

        if resp.status_code in (403, 429):
            retry_after = resp.headers.get("retry-after")
            suffix = f" Retry-After: {retry_after}." if retry_after else ""
            raise RateLimitError(
                f"Backloggd denied or rate-limited the request (HTTP {resp.status_code}) "
                f"for {resp.url}.{suffix}"
            )

        resp.raise_for_status()

    def _request_with_retry(
        self,
        method: str,
        url: str,
        resource_type: str = "resource",
        params: Optional[dict] = None,
    ) -> httpx.Response:
        """Execute HTTP request with automatic transient retry on network drops or 5xx."""
        client = self._get_client()
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("HTTP %s %s (params=%s, attempt=%d)", method, url, params, attempt + 1)
                resp = client.request(method, url, params=params)
                if resp.status_code in (500, 502, 503, 504) and attempt < self.max_retries:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(
                        "HTTP %d on %s, retrying in %.2fs (attempt %d/%d)",
                        resp.status_code, url, wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                    continue

                self._check_response(resp, resource_type=resource_type)
                return resp
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(
                        "Transport error (%s) on %s, retrying in %.2fs (attempt %d/%d)",
                        exc, url, wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("Failed request %s %s after %d retries: %s", method, url, self.max_retries, exc)
                    raise

        if last_exc:
            raise last_exc
        raise BackloggdError(f"Request failed: {url}")

    @staticmethod
    def clean_username(profile_or_username: str) -> str:
        """Extract clean username from a URL or raw username string."""
        clean = profile_or_username.strip()
        if "/u/" in clean:
            return clean.split("/u/")[1].split("/")[0]
        return clean.strip("/")

    @staticmethod
    def clean_slug(game_or_slug: str) -> str:
        """Extract clean game slug from URL or string."""
        clean = game_or_slug.strip()
        if "/games/" in clean:
            return clean.split("/games/")[1].split("/")[0]
        return clean.strip("/")

    # ==================== Game Search ====================

    def search_games(self, query: str, page: int = 1) -> list[GameSearchResult]:
        """Search Backloggd for games by title."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # Turbo stream search
        url = f"{BASE_URL}/search/results.turbo_stream"
        params = {"query": clean_query, "page": page, "type": "games"}
        try:
            resp = self._request_with_retry("GET", url, params=params)
            results = parse_game_search_results(resp.text)
            if results:
                return results
        except Exception as exc:
            logger.debug("Turbo stream search failed (%s), trying search page fallback", exc)

        fallback_url = f"{BASE_URL}/search/games/{clean_query}/"
        resp = self._request_with_retry("GET", fallback_url)
        return parse_game_search_results(resp.text)

    # ==================== User Library & Comparison ====================

    def _fetch_single_page(self, url: str, page: int) -> tuple[int, list[GameEntry], bool]:
        """Fetch and parse one page synchronously."""
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
        page_games, has_more = parse_games_page(resp.text)
        return page, page_games, has_more

    def get_user_library(
        self,
        username: str,
        sort: Optional[str] = None,
        filter: Optional[Union[str, dict]] = None,
        max_pages: Optional[int] = None,
        force_refresh: bool = False,
        on_page: Optional[Callable[[int, list, int], None]] = None,
    ) -> UserLibrary:
        """Fetch games logged by a user synchronously with optional sort, filter, caching, and concurrency."""
        user = self.clean_username(username)
        is_unfiltered = (sort is None and not filter)

        # 1. Cache hit check (only for unfiltered master library)
        if not force_refresh and max_pages is None and is_unfiltered:
            cached = self.cache.get_library(user)
            if cached is not None:
                logger.debug("Cache hit for user library: %s", user)
                return cached

        logger.debug("Cache miss for user library: %s", user)
        base_url = f"{BASE_URL}/u/{user}/games"
        url = build_games_url(base_url, sort=sort, filter=filter)
        library = UserLibrary(username=user)

        # 2. Fetch Page 1 first
        resp1 = self._request_with_retry("GET", url, resource_type="user", params={"page": 1})
        p1_games, p1_has_more = parse_games_page(resp1.text)
        library.update(p1_games)

        if on_page:
            try:
                on_page(1, p1_games, len(library))
            except Exception:
                pass

        if not p1_has_more or (max_pages is not None and max_pages <= 1):
            if max_pages is None and is_unfiltered:
                self.cache.set_library(library)
            return library

        # 3. Concurrent Batched Fetching using ThreadPoolExecutor
        current_page = 2
        batch_size = self.max_concurrency

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            while True:
                if max_pages is not None and current_page > max_pages:
                    break

                target_batch_end = current_page + batch_size
                if max_pages is not None:
                    target_batch_end = min(target_batch_end, max_pages + 1)

                pages_to_fetch = list(range(current_page, target_batch_end))
                if not pages_to_fetch:
                    break

                futures = [executor.submit(self._fetch_single_page, url, p) for p in pages_to_fetch]
                results = [f.result() for f in futures]
                results.sort(key=lambda r: r[0])

                reached_end = False
                for page_num, page_games, has_more in results:
                    if not page_games:
                        reached_end = True
                        break

                    new_slugs = {g.slug for g in page_games} - library.slugs
                    if not new_slugs and len(library) > 0:
                        reached_end = True
                        break

                    library.update(page_games)

                    if on_page:
                        try:
                            on_page(page_num, page_games, len(library))
                        except Exception:
                            pass

                    if not has_more:
                        reached_end = True
                        break

                if reached_end:
                    break

                current_page = target_batch_end

        if max_pages is None and is_unfiltered:
            self.cache.set_library(library)

        return library

    # ==================== User Profile ====================

    def get_user_profile(
        self,
        username: str,
        force_refresh: bool = False,
        **kwargs,
    ) -> UserProfile:
        """Fetch a user's profile metadata directly from /u/<username>/ synchronously."""
        user = self.clean_username(username)

        if not force_refresh:
            cached = self.cache.get_profile(user)
            if cached is not None:
                logger.debug("Cache hit for user profile: %s", user)
                return cached

        logger.debug("Cache miss for user profile: %s", user)
        url = f"{BASE_URL}/u/{user}/"
        resp = self._request_with_retry("GET", url, resource_type="user")
        profile = parse_user_profile_page(resp.text, username=user)
        self.cache.set_profile(profile)
        return profile

    def compare_users(
        self,
        user1: str,
        user2: str,
        max_pages: Optional[int] = None,
        force_refresh: bool = False,
        k_shrinkage: int = 10,
    ) -> MatchComparison:
        """Fetch both users and compute taste comparison & recommendations synchronously."""
        u1_clean = self.clean_username(user1)
        u2_clean = self.clean_username(user2)

        lib1 = self.get_user_library(u1_clean, max_pages=max_pages, force_refresh=force_refresh)
        lib2 = self.get_user_library(u2_clean, max_pages=max_pages, force_refresh=force_refresh)

        return compare_libraries(lib1, lib2, k_shrinkage=k_shrinkage)

    # ==================== Individual Game Details ====================

    def get_game(self, slug_or_url: str, force_refresh: bool = False) -> GameDetails:
        """Fetch full metadata for a game from Backloggd."""
        slug = self.clean_slug(slug_or_url)

        if not force_refresh:
            cached = self.cache.get_game(slug)
            if cached is not None:
                logger.debug("Cache hit for game: %s", slug)
                return cached

        logger.debug("Cache miss for game: %s", slug)
        url = f"{BASE_URL}/games/{slug}/"
        resp = self._request_with_retry("GET", url, resource_type="game")

        game = parse_game_page(resp.text, slug=slug)
        self.cache.set_game(game)
        return game

    # ==================== User Reviews ====================

    def get_user_reviews(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[Review]:
        """Fetch written reviews published by a user."""
        user = self.clean_username(username)
        url = f"{BASE_URL}/u/{user}/reviews/"

        reviews: list[Review] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            page_reviews, has_more = parse_user_reviews_page(resp.text, author=user)
            if not page_reviews:
                break

            reviews.extend(page_reviews)
            for r in page_reviews:
                if r.review_id:
                    self.cache.set_review(r)

            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return reviews

    def get_review(self, review_id: Union[str, int], force_refresh: bool = False) -> Review:
        """Fetch a single standalone review by review_id."""
        rev_id_str = str(review_id).strip()

        if not force_refresh:
            cached = self.cache.get_review(rev_id_str)
            if cached is not None:
                logger.debug("Cache hit for review: %s", rev_id_str)
                return cached

        logger.debug("Cache miss for review: %s", rev_id_str)
        url = f"{BASE_URL}/reviews/{rev_id_str}"
        resp = self._request_with_retry("GET", url, resource_type="review")

        review = parse_standalone_review_page(resp.text, review_id=rev_id_str)
        self.cache.set_review(review)
        return review

    # ==================== User Lists ====================

    def get_user_lists(self, username: str) -> list[UserListSummary]:
        """Fetch summaries of custom lists created by a user."""
        user = self.clean_username(username)
        url = f"{BASE_URL}/u/{user}/lists/"
        resp = self._request_with_retry("GET", url, resource_type="user")

        return parse_user_lists_overview(resp.text, author=user)

    def get_list(self, list_url: str, force_refresh: bool = False) -> UserList:
        """Fetch full contents and games of a custom user list."""
        clean_url = list_url.strip()
        if not clean_url.startswith("http"):
            clean_url = f"{BASE_URL}{clean_url}" if clean_url.startswith("/") else f"{BASE_URL}/{clean_url}"

        if not force_refresh:
            cached = self.cache.get_list(clean_url)
            if cached is not None:
                logger.debug("Cache hit for list: %s", clean_url)
                return cached

        logger.debug("Cache miss for list: %s", clean_url)
        resp = self._request_with_retry("GET", clean_url, resource_type="list")

        user_list = parse_single_list_page(resp.text, url=clean_url)
        self.cache.set_list(user_list)
        return user_list

    # ==================== Social Network (Followers, Following, Friends) ====================

    def get_user_following(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[UserSummary]:
        """Fetch users followed by the specified user (/u/<user>/following/) synchronously."""
        user = self.clean_username(username)
        url = f"{BASE_URL}/u/{user}/following/"
        following: list[UserSummary] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            page_users, has_more = parse_user_social_page(resp.text)
            if not page_users:
                break

            following.extend(page_users)
            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return following

    def get_user_followers(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[UserSummary]:
        """Fetch followers of the specified user (/u/<user>/followers/) synchronously."""
        user = self.clean_username(username)
        url = f"{BASE_URL}/u/{user}/followers/"
        followers: list[UserSummary] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            page_users, has_more = parse_user_social_page(resp.text)
            if not page_users:
                break

            followers.extend(page_users)
            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return followers

    def get_user_friends(
        self,
        username: str,
    ) -> list[UserSummary]:
        """Fetch mutual followers (friends) of the specified user synchronously."""
        user = self.clean_username(username)
        following = self.get_user_following(user)
        followers = self.get_user_followers(user)
        follower_map = {u.username.lower(): u for u in followers}
        return [u for u in following if u.username.lower() in follower_map]

    # ==================== Targeted Collections (Playing, Backlog, Wishlist) ====================

    def get_user_playing(
        self,
        username: str,
        sort: Optional[str] = None,
    ) -> list[GameEntry]:
        """Fetch games currently being played by the user (/games/playing/) synchronously."""
        user = self.clean_username(username)
        if sort:
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter="type:playing")
        else:
            url = f"{BASE_URL}/u/{user}/games/playing/"
        resp = self._request_with_retry("GET", url, resource_type="user")
        games, _ = parse_games_page(resp.text)
        return games

    def get_user_backlog(
        self,
        username: str,
        sort: Optional[str] = None,
        filter: Optional[Union[str, dict]] = None,
        max_pages: Optional[int] = None,
    ) -> list[GameEntry]:
        """Fetch games in the user's backlog with optional sort and filter synchronously."""
        user = self.clean_username(username)
        if isinstance(filter, dict):
            f_copy = dict(filter)
            f_copy["type"] = "backlog"
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter=f_copy)
        elif isinstance(filter, str) and filter.strip():
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter=f"type:backlog;{filter.strip()}")
        elif sort:
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter="type:backlog")
        else:
            url = f"{BASE_URL}/u/{user}/games/backlog/"

        backlog_games: list[GameEntry] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            games, has_more = parse_games_page(resp.text)
            if not games:
                break

            backlog_games.extend(games)
            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return backlog_games

    def get_user_wishlist(
        self,
        username: str,
        sort: Optional[str] = None,
        filter: Optional[Union[str, dict]] = None,
        max_pages: Optional[int] = None,
    ) -> list[GameEntry]:
        """Fetch games on the user's wishlist with optional sort and filter synchronously."""
        user = self.clean_username(username)
        if isinstance(filter, dict):
            f_copy = dict(filter)
            f_copy["type"] = "wishlist"
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter=f_copy)
        elif isinstance(filter, str) and filter.strip():
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter=f"type:wishlist;{filter.strip()}")
        elif sort:
            url = build_games_url(f"{BASE_URL}/u/{user}/games", sort=sort, filter="type:wishlist")
        else:
            url = f"{BASE_URL}/u/{user}/games/wishlist/"

        wishlist_games: list[GameEntry] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            games, has_more = parse_games_page(resp.text)
            if not games:
                break

            wishlist_games.extend(games)
            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return wishlist_games

    # ==================== Global Games Catalog Browsing ====================

    def browse_games(
        self,
        sort: str = "popular",
        filter: Optional[Union[str, dict]] = None,
        max_pages: int = 1,
        on_page: Optional[Callable[[int, list[GameEntry], int], None]] = None,
    ) -> list[GameEntry]:
        """Browse the global Backloggd games catalog (/games/lib/{sort}/{filters}/) synchronously."""
        base_url = f"{BASE_URL}/games/lib"
        url = build_games_url(base_url, sort=sort, filter=filter)
        games: list[GameEntry] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="game", params={"page": page})
            page_games, has_more = parse_games_page(resp.text)
            if not page_games:
                break

            games.extend(page_games)
            if on_page:
                try:
                    on_page(page, page_games, len(games))
                except Exception:
                    pass

            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return games

    # ==================== User Play Journal ====================

    def get_user_journal(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[JournalEntry]:
        """Fetch playthrough journal logs for a user (/u/<user>/journal/) synchronously."""
        user = self.clean_username(username)
        url = f"{BASE_URL}/u/{user}/journal/"
        journal_entries: list[JournalEntry] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="user", params={"page": page})
            entries, has_more = parse_journal_page(resp.text)
            if not entries:
                break

            journal_entries.extend(entries)
            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return journal_entries

    # ==================== Community Game Reviews ====================

    def get_game_reviews(
        self,
        slug_or_url: str,
        max_pages: Optional[int] = None,
    ) -> list[Review]:
        """Fetch community reviews for a game (/games/<slug>/reviews) synchronously."""
        slug = self.clean_slug(slug_or_url)
        url = f"{BASE_URL}/games/{slug}/reviews"
        reviews: list[Review] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                break

            resp = self._request_with_retry("GET", url, resource_type="game", params={"page": page})
            page_reviews, has_more = parse_game_reviews_page(resp.text, default_game_slug=slug)
            if not page_reviews:
                break

            reviews.extend(page_reviews)
            for r in page_reviews:
                if r.review_id:
                    self.cache.set_review(r)

            if not has_more:
                break

            page += 1
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        return reviews
