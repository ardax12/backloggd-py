"""Play journal log models for Backloggd."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, frozen=True)
class JournalEntry:
    """A log entry recorded in a user's Backloggd playthrough journal."""
    entry_id: str
    game_title: str
    game_slug: str
    played_date: Optional[str] = None
    platform: Optional[str] = None
    rating: Optional[float] = None
    is_replay: bool = False
    review_notes: Optional[str] = None
    cover_url: Optional[str] = None

    @property
    def url(self) -> str:
        """Full URL to the game's page."""
        return f"https://backloggd.com/games/{self.game_slug}/"
