import pytest
from backloggd import Backloggd
from backloggd.models.game import GameStatus


def test_sync_client_profile_and_stats():
    with Backloggd() as client:
        profile = client.get_user_profile("ardax12")
        assert profile.username == "ardax12"
        assert profile.url == "https://backloggd.com/u/ardax12/"

        library = client.get_user_library("ardax12", max_pages=1)
        assert library.username == "ardax12"
        assert len(library) > 0

        profile.library = library
        stats = profile.get_stats()
        assert stats.total_games == len(library)
        assert stats.rated_count > 0
        assert stats.average_rating is not None

        # Test filter
        high_rated = library.filter(min_rating=4.0)
        assert len(high_rated) > 0



def test_sync_client_compare():
    with Backloggd() as client:
        comp = client.compare_users("ardax12", "nehir", max_pages=1)
        assert comp.user1 == "ardax12"
        assert comp.user2 == "nehir"
        assert comp.similarity_score > 0
        assert len(comp.recommendations_for_user1) > 0
