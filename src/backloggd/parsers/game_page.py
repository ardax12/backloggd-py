"""HTML parser for Backloggd individual game pages."""

import re
from typing import Optional
from bs4 import BeautifulSoup
from backloggd.models.game import GameDetails, GameStatsSummary


def parse_game_page(html: str, slug: str) -> GameDetails:
    """Parse a game page into a GameDetails model."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Title extraction
    title = slug.replace("-", " ").title()
    h1 = soup.select_one("#game-title, .game-title, h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    # Release year from title or subtitle
    year: Optional[int] = None
    if soup.title and soup.title.string:
        match = re.search(r"\((\d{4})\)", soup.title.string)
        if match:
            year = int(match.group(1))

    # Community rating (e.g. 4.5 in H1 or rating container)
    rating: Optional[float] = None
    for h in soup.find_all("h1"):
        txt = h.get_text(strip=True)
        try:
            val = float(txt)
            if 0.0 <= val <= 5.0:
                rating = val
                break
        except ValueError:
            pass

    # Summary description
    summary: Optional[str] = None
    p_desc = soup.select_one(".game-description, #game-description, .summary")
    if p_desc:
        summary = p_desc.get_text(strip=True)
    else:
        # Fallback to main narrative paragraph
        for p in soup.find_all("p"):
            t = p.get_text(strip=True)
            if len(t) > 60 and not t.startswith("Cookies") and "IGDB" not in t:
                summary = t
                break

    # Cover image and game ID
    cover_img = soup.select_one(".card-img, .game-cover img, img[src*='images.igdb.com']")
    cover_url = cover_img.get("src") if cover_img else None

    game_cover = soup.select_one(".game-cover")
    game_id = game_cover.get("game_id") if game_cover else None

    # Community engagement numbers (Plays, Backlogs, Wishlists)
    plays_count: Optional[str] = None
    backlogs_count: Optional[str] = None
    wishlists_count: Optional[str] = None

    stat_cards = soup.select(".col-4, .stat-card, [class*='stat']")
    h3_stats = [h.get_text(strip=True) for h in soup.find_all("h3")]
    # Backloggd displays 3 counts in H3 right below 'Backloggd Stats'
    stat_nums = [h for h in h3_stats if any(c.isdigit() for c in h)]
    if len(stat_nums) >= 3:
        plays_count = stat_nums[0]
        backlogs_count = stat_nums[1]
        wishlists_count = stat_nums[2]

    stats = GameStatsSummary(
        plays_count=plays_count,
        backlogs_count=backlogs_count,
        wishlists_count=wishlists_count,
    )

    return GameDetails(
        slug=slug,
        title=title,
        release_year=year,
        community_rating=rating,
        summary=summary,
        cover_url=cover_url,
        game_id=game_id,
        stats=stats,
    )
