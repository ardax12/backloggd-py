from bs4 import BeautifulSoup
from backloggd.parsers.profile import parse_user_profile_page
from backloggd.parsers.reviews import parse_review_card


def test_profile_avatar_bio_and_short_url_without_runtime_patches():
    html = '<div id="profile-header"><img class="profile-avatar" src="/avatars/test.jpg"><p class="profile-bio">First line.<br>Second line.</p></div><button short_url="https://bckl.gg/test">Share</button>'
    profile = parse_user_profile_page(html, "testuser")
    assert profile.avatar_url == "https://backloggd.com/avatars/test.jpg"
    assert profile.bio == "First line. Second line."
    assert profile.short_url == "https://bckl.gg/test"


def test_review_paragraphs_do_not_run_together():
    card = BeautifulSoup('<div class="user-reviews"><div class="game-name"><a href="/games/hades/">Hades</a></div><div class="review-text"><p>Great game,</p><p>loved the combat!</p></div></div>', "html.parser")
    assert parse_review_card(card).review_text == "Great game, loved the combat!"
