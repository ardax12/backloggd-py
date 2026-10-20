"""Backloggd Python SDK and Taste Matcher."""

from backloggd.client import BackloggdClient
from backloggd.sync_client import Backloggd
from backloggd.cache import CacheManager
from backloggd.utils import load_cookies, build_games_url
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
from backloggd.models import (
    GameDetails,
    GameEntry,
    GameSearchResult,
    GameStatsSummary,
    GameStatus,
    MatchComparison,
    RatingDisagreement,
    Review,
    UserLibrary,
    UserList,
    UserListSummary,
    UserProfile,
    UserStats,
    UserSummary,
    JournalEntry,
)
from backloggd.analytics.matcher import calculate_similarity_raw, compare_libraries

__version__ = "0.1.0"

__all__ = [
    # Clients, Cache & Utilities
    "Backloggd",            # Synchronous client (no async/await needed)
    "BackloggdClient",      # Async client
    "CacheManager",
    "load_cookies",
    "build_games_url",
    # Models
    "GameEntry",
    "GameDetails",
    "GameSearchResult",
    "GameStatsSummary",
    "GameStatus",
    "Review",
    "UserList",
    "UserListSummary",
    "UserLibrary",
    "UserProfile",
    "UserStats",
    "UserSummary",
    "JournalEntry",
    "MatchComparison",
    "RatingDisagreement",
    # Analytics
    "calculate_similarity_raw",
    "compare_libraries",
    # Exceptions
    "BackloggdError",
    "ChallengeResponseError",
    "RateLimitError",
    "ResourceNotFoundError",
    "UserNotFoundError",
    "GameNotFoundError",
    "ListNotFoundError",
    "ReviewNotFoundError",
]

