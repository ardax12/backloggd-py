"""Data models for Backloggd games, details, and community stats."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class GameStatus(str, Enum):
    """Playing status on Backloggd."""
    PLAYED = "played"
    PLAYING = "playing"
    BACKLOG = "backlog"
    WISHLIST = "wishlist"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class GameEntry:
    """Represents a game entry in a user's Backloggd library."""
    slug: str
    title: str
    rating: Optional[float] = None
    status: GameStatus = GameStatus.UNKNOWN
    status_title: Optional[str] = None
    is_liked: bool = False
    cover_url: Optional[str] = None
    game_id: Optional[str] = None
    log_id: Optional[str] = None
    logged_at: Optional[datetime] = None

    @property
    def is_rated(self) -> bool:
        """Return True if the game has a rating."""
        return self.rating is not None

    @property
    def url(self) -> str:
        """Full URL to the game's Backloggd page."""
        return f"https://backloggd.com/games/{self.slug}/"


@dataclass(slots=True, frozen=True)
class GameStatsSummary:
    """Community metrics for a game on Backloggd."""
    plays_count: Optional[str] = None       # e.g., "8.5K"
    backlogs_count: Optional[str] = None    # e.g., "3.5K"
    wishlists_count: Optional[str] = None   # e.g., "5.9K"


@dataclass(slots=True, frozen=True)
class GameDetails:
    """Full metadata for a game fetched from its Backloggd game page."""
    slug: str
    title: str
    release_year: Optional[int] = None
    community_rating: Optional[float] = None   # e.g. 4.5
    summary: Optional[str] = None
    cover_url: Optional[str] = None
    game_id: Optional[str] = None
    stats: GameStatsSummary = field(default_factory=GameStatsSummary)

    @property
    def url(self) -> str:
        """Full URL to the game's Backloggd page."""
        return f"https://backloggd.com/games/{self.slug}/"


@dataclass(slots=True, frozen=True)
class GameSearchResult:
    """Represents a game entry returned from a Backloggd search query."""
    title: str
    slug: str
    release_year: Optional[int] = None
    cover_url: Optional[str] = None
    game_id: Optional[str] = None
    platforms: list[str] = field(default_factory=list)
    game_type: Optional[str] = None

    @property
    def url(self) -> str:
        """Full URL to the game's Backloggd page."""
        return f"https://backloggd.com/games/{self.slug}/"
