"""Common utilities, HTTP constants, URL builders, and cookie parsers."""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("backloggd")

BASE_URL = "https://backloggd.com"
DEFAULT_COOKIES_FILE = "cookies.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SORT_ALIASES: dict[str, str] = {
    "rating": "rating",
    "rating_desc": "rating",
    "rating_high": "rating",
    "popular": "popular",
    "popularity": "popular",
    "release": "release",
    "release_date": "release",
    "year": "release",
    "title": "title",
    "alphabetical": "title",
    "name": "title",
    "last_played": "last_played",
    "recent": "last_played",
    "played": "played",
    "plays": "played",
}

FILTER_KEY_ALIASES: dict[str, str] = {
    "platform": "release_platform",
    "platforms": "release_platform",
    "year": "release_year",
    "years": "release_year",
    "rating": "game_rating",
    "ratings": "game_rating",
}


def load_cookies(cookies_path: Optional[Union[str, Path]] = None) -> dict[str, str]:
    """Load session cookies from environment variable BACKLOGGD_SESSION or JSON file."""
    cookies: dict[str, str] = {}

    # 1. Environment variable directly containing session value
    env_session = os.getenv("BACKLOGGD_SESSION")
    if env_session:
        cookies["_backloggd_session"] = env_session.strip()

    # 2. File-based cookies
    if cookies_path is None:
        local_path = Path("cookies.local.json")
        if local_path.is_file():
            cookies_path = local_path
        else:
            cookies_path = os.getenv("BACKLOGGD_COOKIES_PATH", DEFAULT_COOKIES_FILE)

    path = Path(cookies_path)
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cookies[str(item["name"])] = str(item["value"])
            elif isinstance(data, dict):
                for k, v in data.items():
                    cookies[str(k)] = str(v)
        except Exception as exc:
            logger.debug("Failed reading cookies file %s: %s", path, exc)

    return cookies


def build_games_url(
    base_url: str,
    sort: Optional[str] = None,
    filter: Optional[Union[str, dict]] = None,
) -> str:
    """Build a canonical Backloggd games URL with path-based sort and filters."""
    url = base_url.rstrip("/")

    canonical_sort = None
    if sort:
        clean_sort = str(sort).lower().strip()
        canonical_sort = SORT_ALIASES.get(clean_sort, clean_sort)

    filter_str = None
    if isinstance(filter, dict):
        pairs = []
        for k, v in filter.items():
            if v is not None:
                clean_k = str(k).lower().strip()
                canonical_k = FILTER_KEY_ALIASES.get(clean_k, clean_k)
                clean_v = str(v).replace(".", "_") if isinstance(v, float) else str(v)
                pairs.append(f"{canonical_k}:{clean_v}")
        if pairs:
            filter_str = ";".join(pairs)
    elif isinstance(filter, str) and filter.strip():
        filter_str = filter.strip()

    if canonical_sort:
        url = f"{url}/{canonical_sort}"
    if filter_str:
        url = f"{url}/{filter_str}"

    return url


def clean_username(profile_or_username: str) -> str:
    """Extract clean username from a URL or raw username string."""
    clean = profile_or_username.strip()
    if "/u/" in clean:
        return clean.split("/u/")[1].split("/")[0]
    return clean.strip("/")


def clean_slug(game_or_slug: str) -> str:
    """Extract clean game slug from URL or string."""
    clean = game_or_slug.strip()
    if "/games/" in clean:
        return clean.split("/games/")[1].split("/")[0]
    return clean.strip("/")
