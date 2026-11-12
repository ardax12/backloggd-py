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

    # 1. Avatar URL: check OpenGraph/Twitter meta tags first (Backloggd standard), then HTML selectors
    avatar_url: Optional[str] = None
    og_image = soup.select_one("meta[property='og:image'], meta[name='og:image'], meta[property='twitter:image']")
    if og_image and og_image.get("content"):
        content_url = og_image["content"].strip()
        if content_url and not any(k in content_url for k in ["no_avatar.jpg", "no_avatar.png", "default_avatar"]):
            if content_url.startswith("//"):
                content_url = f"https:{content_url}"
            elif content_url.startswith("/"):
                content_url = f"https://backloggd.com{content_url}"
            avatar_url = content_url

    if not avatar_url:
        avatar_selectors = [
            "#profile-header img",
            "img.profile-avatar",
            ".profile-avatar img",
            ".user-avatar img",
            "img.user-avatar",
            ".avatar img",
            "img.avatar",
            "[class*='avatar'] img",
            "img[class*='avatar']",
            "img[src*='avatar']",
            "img[src*='avatars']",
            "img[src*='backloggd-avatars']",
            ".profile-pic img",
            "img.profile-pic",
            "img[alt*='avatar']",
            "img[alt*='profile']",
            ".user-details img"
        ]
        for selector in avatar_selectors:
            avatar_img = soup.select_one(selector)
            if avatar_img:
                src = avatar_img.get("src") or avatar_img.get("data-src") or avatar_img.get("data-original")
                if src and not any(k in src for k in ["no_avatar.jpg", "no_avatar.png", "default_avatar"]):
                    if src.startswith("//"):
                        src = f"https:{src}"
                    elif src.startswith("/"):
                        src = f"https://backloggd.com{src}"
                    avatar_url = src
                    break

        if not avatar_url:
            avatar_url = "https://backloggd.b-cdn.net/no_avatar.jpg"

    # 2. Bio text: check #bio-body first (Backloggd DOM container), then other profile bio selectors
    bio: Optional[str] = None
    bio_selectors = [
        "#bio-body",
        "#profile-bio",
        "#bio",
        ".profile-bio",
        ".user-bio",
        "p.bio",
        ".profile-description",
        "#profile-description",
        ".user-description",
        "#user-bio",
        ".bio-content",
        ".about-me",
        "#about-me",
        ".profile-about",
        "#profile-header p",
        ".user-details p",
        "div[class*='bio']",
        "p[class*='bio']"
    ]
    for selector in bio_selectors:
        bio_el = soup.select_one(selector)
        if bio_el:
            # Replace line breaks and paragraph tags with spaces so words never combine
            for br in bio_el.find_all(["br", "p", "div"]):
                br.insert_after(" ")
            raw_text = bio_el.get_text()
            if raw_text:
                # Normalize spaces and fix combined words
                cleaned = re.sub(r"[\r\n]+", " ", raw_text)
                cleaned = re.sub(r"([a-zA-Z0-9]),([a-zA-Z])", r"\1, \2", cleaned)
                cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                if cleaned and cleaned.lower() not in ["nothing here!", "nothing here."] and not any(k in cleaned.lower() for k in ["edit profile", "settings", "followers", "following"]):
                    bio = cleaned
                    break

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
