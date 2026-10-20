"""HTML parser for Backloggd followers and following lists."""

from typing import Optional
from bs4 import BeautifulSoup
from backloggd.models.user import UserSummary


def parse_user_social_page(html: str) -> tuple[list[UserSummary], bool]:
    """Parse a following or followers page into a list of UserSummary items.

    Returns:
        tuple[list[UserSummary], bool]: (users_list, has_more_pages)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    users: list[UserSummary] = []
    seen: set[str] = set()

    # User entries on social pages reside in user-card or cards with links to /u/<username>/
    for a in soup.find_all("a", href=lambda h: bool(h and h.startswith("/u/") and h.count("/") == 3)):
        href = a.get("href", "").strip("/")
        parts = href.split("/")
        if len(parts) != 2:
            continue

        username = parts[1]
        if username in seen or username.lower() in ("settings", "games", "lists", "reviews", "journal"):
            continue

        # Look for avatar image inside link or adjacent card
        img = a.find("img")
        if not img:
            parent = a.find_parent("div")
            if parent:
                img = parent.select_one("img[src*='avatar'], .avatar img, img")

        avatar_url: Optional[str] = None
        if img and img.get("src"):
            src = img["src"]
            if not src.endswith("no_avatar.jpg"):
                avatar_url = src

        seen.add(username)
        users.append(UserSummary(username=username, avatar_url=avatar_url))

    # Backloggd uses standard pagination (typically 30 or 40 items per page)
    # Check if a next page button / link exists
    next_btn = soup.find("a", rel=lambda r: bool(r and "next" in r)) or soup.find("a", string=lambda s: bool(s and "Next" in s))
    has_more = bool(next_btn)

    return users, has_more
