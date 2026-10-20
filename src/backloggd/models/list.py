"""Data models for Backloggd custom user lists."""

from dataclasses import dataclass, field
from typing import Optional
from backloggd.models.game import GameEntry


@dataclass(slots=True, frozen=True)
class UserListSummary:
    """Brief metadata for a list shown in user's lists overview."""
    title: str
    slug: str
    author: str
    url: str


@dataclass(slots=True, frozen=True)
class UserList:
    """Full user list with its games."""
    title: str
    slug: str
    author: str
    url: str
    description: Optional[str] = None
    games: list[GameEntry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.games)
