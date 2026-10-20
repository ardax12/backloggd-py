"""User profile models, user summaries, and library statistics."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from backloggd.models.library import UserLibrary, UserStats

if TYPE_CHECKING:
    from backloggd.models.game import GameEntry


@dataclass(slots=True, frozen=True)
class UserSummary:
    """Lightweight representation of a Backloggd user (for followers/following/friends)."""
    username: str
    avatar_url: Optional[str] = None

    @property
    def url(self) -> str:
        """Full URL to user's profile."""
        return f"https://backloggd.com/u/{self.username}/"


@dataclass(slots=True)
class UserProfile:
    """User profile metadata scraped directly from /u/<username>/."""
    username: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    favorite_games: list = field(default_factory=list)  # list[GameEntry]
    badges: list[str] = field(default_factory=list)
    short_url: Optional[str] = None
    played_count: Optional[int] = None
    playing_count: Optional[int] = None
    backlog_count: Optional[int] = None
    wishlist_count: Optional[int] = None
    library: Optional[UserLibrary] = None

    @property
    def url(self) -> str:
        """Full URL to user's profile."""
        return f"https://backloggd.com/u/{self.username}/"

    def get_stats(self) -> Optional[UserStats]:
        """Compute library statistics and rating distribution if library is populated."""
        if self.library is not None:
            return self.library.get_stats()
        return None

