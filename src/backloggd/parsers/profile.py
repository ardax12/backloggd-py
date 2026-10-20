"""HTML parser for Backloggd user profile pages."""

import re
from typing import Optional
from bs4 import BeautifulSoup, NavigableString, TemplateString, Tag
from backloggd.models.game import GameEntry
from backloggd.models.user import UserProfile

TEXT_TYPES = (NavigableString, TemplateString)


def _clean_text(tag: Optional[Tag], strip: bool = True) -> str:
    if tag is None:
        return ""
    txt = tag.get_text(separator=" ", strip=strip, types=TEXT_TYPES)
    return txt.strip() if strip else txt


def parse_user_profile_page(html: str, username: str) -> UserProfile:
    """Parse a user profile overview page (/u/<username>/) into a UserProfile model."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # 1. Avatar URL
    avatar_url: Optional[str] = None
    avatar_img = soup.select_one(".avatar img, [class*='avatar'] img, img[src*='backloggd-avatars']")
    if avatar_img and avatar_img.get("src"):
        src = avatar_img["src"]
        if not src.endswith("no_avatar.jpg"):
            avatar_url = src

    # 2. Bio text
    bio: Optional[str] = None
    bio_el = soup.select_one("#profile-bio, #bio, .profile-bio, .user-bio, .bio")
    if bio_el:
        bio_text = _clean_text(bio_el)
        if bio_text:
            bio = bio_text

    # 3. Short URL
    short_url: Optional[str] = None
    short_btn = soup.select_one("button[short_url], .short-url, [short_url]")
    if short_btn and short_btn.get("short_url"):
        short_url = short_btn["short_url"]

    # 4. Badges
    badges: list[str] = []
    badge_imgs = soup.select("img[src*='badges'], .badge img, [class*='badge'] img")
    for b in badge_imgs:
        src = b.get("src", "")
        if "badge" in src:
            # Extract badge name from filename, e.g. "goty-2025.svg" -> "goty-2025"
            fname = src.split("/")[-1].split(".")[0].replace("replay-", "replay_").replace("goty-", "goty_")
            if fname and fname not in badges:
                badges.append(fname)

    # 5. Favorite / Pinned Games (#profile-favorites)
    favorite_games: list[GameEntry] = []
    fav_section = soup.select_one("#profile-favorites, .favorite-games, #favorites")
    if fav_section:
        covers = fav_section.select(".game-cover")
        for c in covers:
            img = c.select_one("img")
            title = img.get("alt", "").strip() if img else ""
            cover_url = img.get("src") if img else None
            game_id = c.get("game_id")

            # Game link
            link = c.find_parent("a", href=lambda h: bool(h and "/games/" in h)) or c.find("a", href=lambda h: bool(h and "/games/" in h))
            slug = ""
            if link and link.get("href"):
                slug = link["href"].strip("/").split("/")[-1]
            elif title:
                slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "")

            if title and slug and slug not in {g.slug for g in favorite_games}:
                favorite_games.append(
                    GameEntry(
                        slug=slug,
                        title=title,
                        cover_url=cover_url,
                        game_id=game_id,
                    )
                )

    # 6. Quick Counts from header/nav
    played_count: Optional[int] = None
    playing_count: Optional[int] = None
    backlog_count: Optional[int] = None
    wishlist_count: Optional[int] = None

    # Search links with counters e.g. /games/, /playing/, /backlog/, /wishlist/
    clean_user = username.lower().strip()
    for a in soup.find_all("a", href=lambda h: bool(h and f"/u/{clean_user}/" in h.lower())):
        href = a.get("href", "").lower()
        text = _clean_text(a)
        num_match = re.search(r"(\d+[\d,]*)", text)
        if not num_match:
            continue
        count_val = int(num_match.group(1).replace(",", ""))

        if "/playing" in href and playing_count is None:
            playing_count = count_val
        elif "/backlog" in href and backlog_count is None:
            backlog_count = count_val
        elif "/wishlist" in href and wishlist_count is None:
            wishlist_count = count_val
        elif "/games" in href and played_count is None and not any(k in href for k in ["backlog", "wishlist", "playing"]):
            played_count = count_val

    return UserProfile(
        username=username,
        avatar_url=avatar_url,
        bio=bio,
        favorite_games=favorite_games,
        badges=badges,
        short_url=short_url,
        played_count=played_count,
        playing_count=playing_count,
        backlog_count=backlog_count,
        wishlist_count=wishlist_count,
    )
