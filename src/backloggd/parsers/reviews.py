"""HTML parser for Backloggd reviews."""

import re
from typing import Optional
from bs4 import BeautifulSoup, Tag
from backloggd.models.review import Review


def parse_review_card(
    card: Tag,
    default_author: Optional[str] = None,
    default_game_slug: str = "",
    default_game_title: str = "",
) -> Optional[Review]:
    """Parse a single review card."""
    # Find game title and slug
    game_a = card.select_one(".game-name a, h3 a, a[href*='/games/']")
    if game_a:
        game_title = game_a.get_text(strip=True)
        slug = game_a.get("href", "").strip("/").split("/")[-1]
    else:
        game_title = default_game_title
        slug = default_game_slug

    if not slug and not game_title:
        return None

    # Author
    author = default_author or ""
    author_a = card.find("a", href=lambda h: bool(h and "/u/" in h and "/review/" not in h))
    if author_a and author_a.get_text(strip=True):
        author = author_a.get_text(strip=True)

    # Review ID & URL
    review_link = card.find("a", href=lambda h: bool(h and "/review/" in h))
    review_id = ""
    if review_link and review_link.get("href"):
        match = re.search(r"/review/(\d+)/", review_link["href"])
        if match:
            review_id = match.group(1)

    # Rating from stars-top width
    rating: Optional[float] = None
    stars_top = card.select_one(".stars-top")
    if stars_top and "width:" in stars_top.get("style", ""):
        try:
            w = stars_top["style"].split("width:")[1].split("%")[0].strip()
            rating = float(w) / 20.0
        except (ValueError, IndexError):
            pass

    # Review written text
    review_text = ""
    # Review body is usually inside card-text or paragraphs
    body_div = card.select_one(".review-text, .card-text, .body-text, .review-body")
    if body_div:
        review_text = body_div.get_text(strip=True)
    else:
        # Fallback to paragraph elements
        for p in card.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 20 and not any(k in txt for k in ["Edit log", "Completed", "Likes"]):
                review_text = txt
                break

    # Like count
    like_count = 0
    like_el = card.find(string=re.compile(r"(\d+)\s+Like"))
    if like_el:
        match = re.search(r"(\d+)", like_el)
        if match:
            like_count = int(match.group(1))

    # Created at date
    created_at = None
    date_el = card.find(string=re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}"))
    if date_el:
        created_at = date_el.strip()

    # Spoilers
    has_spoilers = bool(card.select_one(".spoiler, .has-spoilers, [class*='spoiler']"))

    return Review(
        review_id=review_id,
        game_title=game_title,
        game_slug=slug,
        author=author,
        rating=rating,
        review_text=review_text,
        created_at=created_at,
        like_count=like_count,
        has_spoilers=has_spoilers,
    )


def parse_user_reviews_page(html: str, author: str) -> tuple[list[Review], bool]:
    """Parse reviews from a user's reviews overview page.

    Returns:
        tuple[list[Review], bool]: (reviews_list, has_more_pages)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(".user-reviews")
    reviews: list[Review] = []

    for c in cards:
        # Skip header info card
        if not c.select_one(".game-name"):
            continue
        rev = parse_review_card(c, default_author=author)
        if rev and rev.game_title:
            reviews.append(rev)

    # 15 reviews per page
    has_more = len(reviews) >= 15
    return reviews, has_more


def parse_standalone_review_page(html: str, review_id: str) -> Review:
    """Parse a single review page (/u/<user>/review/<id>/)."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    game_a = soup.find("a", href=lambda h: bool(h and "/games/" in h))
    game_title = game_a.get_text(strip=True) if game_a else ""
    slug = game_a.get("href", "").strip("/").split("/")[-1] if game_a else ""

    author = ""
    author_a = soup.find("a", href=lambda h: bool(h and "/u/" in h and "/review/" not in h))
    if author_a:
        author = author_a.get_text(strip=True)

    rating: Optional[float] = None
    stars_top = soup.select_one(".stars-top")
    if stars_top and "width:" in stars_top.get("style", ""):
        try:
            w = stars_top["style"].split("width:")[1].split("%")[0].strip()
            rating = float(w) / 20.0
        except (ValueError, IndexError):
            pass

    review_text = ""
    body = soup.select_one(".review-text, .card-text, .body-text, #review-body")
    if body:
        review_text = body.get_text(strip=True)

    like_count = 0
    like_el = soup.find(string=re.compile(r"(\d+)\s+Like"))
    if like_el:
        match = re.search(r"(\d+)", like_el)
        if match:
            like_count = int(match.group(1))

    return Review(
        review_id=review_id,
        game_title=game_title,
        game_slug=slug,
        author=author,
        rating=rating,
        review_text=review_text,
        like_count=like_count,
    )


def parse_game_reviews_page(
    html: str,
    default_game_slug: str = "",
    default_game_title: str = "",
) -> tuple[list[Review], bool]:
    """Parse reviews from a game's community reviews page or turbo stream.

    Returns:
        tuple[list[Review], bool]: (reviews_list, has_more_pages)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # If game title is in h1/header and not provided
    if not default_game_title:
        header_el = soup.select_one("h1, .game-title, [class*='title']")
        if header_el:
            default_game_title = header_el.get_text(strip=True)

    # Review cards can be .review-card, .user-reviews, .review, or elements containing /review/
    cards = soup.select(".review-card, .user-reviews, .review")
    if not cards:
        seen_parents = set()
        for rev_a in soup.find_all("a", href=lambda h: bool(h and "/review/" in h)):
            p = rev_a.find_parent("div", class_=lambda c: bool(c and any(k in str(c) for k in ["card", "review", "row"])))
            if p and id(p) not in seen_parents:
                seen_parents.add(id(p))
                cards.append(p)

    reviews: list[Review] = []
    seen_ids: set[str] = set()

    for c in cards:
        rev = parse_review_card(
            c,
            default_game_slug=default_game_slug,
            default_game_title=default_game_title,
        )
        if rev and rev.author and (rev.review_id or rev.review_text):
            if rev.review_id:
                if rev.review_id in seen_ids:
                    continue
                seen_ids.add(rev.review_id)
            reviews.append(rev)

    # Check for next page
    next_btn = soup.find("a", rel=lambda r: bool(r and "next" in r)) or soup.find("a", string=lambda s: bool(s and "Next" in s))
    has_more = bool(next_btn) or len(reviews) >= 15

    return reviews, has_more
