"""Typed game activity scraped from a user activity stream."""
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass(slots=True, frozen=True)
class ActivityEntry:
    activity_id: str
    game_title: str
    game_slug: str
    cover_url: Optional[str]
    action_type: str  # "played", "completed", "rated", "reviewed", "backlog", "wishlist"
    action_text: str  # e.g. "played", "rated ★★★★½ (4.5)", "added to backlog"
    rating: Optional[float]
    review_notes: Optional[str]
    date_str: Optional[str]
    occurred_at: Optional[str] = None
    reference: Optional[str] = None
    is_replay: bool = False
    has_spoilers: bool = False


@dataclass(slots=True, frozen=True)
class ActivitySnapshot:
    """A validated activity fetch and an explicit statement of its coverage."""

    entries: list[ActivityEntry]
    coverage: Literal["boundary_reached", "exhausted", "limited", "unsupported"]
    pages_read: int

