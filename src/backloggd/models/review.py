"""Data models for Backloggd reviews."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, frozen=True)
class Review:
    """Represents a written review on Backloggd."""
    review_id: str
    game_title: str
    game_slug: str
    author: str
    rating: Optional[float] = None
    review_text: str = ""
    created_at: Optional[str] = None
    like_count: int = 0
    has_spoilers: bool = False

    @property
    def url(self) -> str:
        """Full URL to the standalone review."""
        return f"https://backloggd.com/u/{self.author}/review/{self.review_id}/"
