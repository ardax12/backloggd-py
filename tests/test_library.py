import pytest
from backloggd.models.game import GameEntry, GameStatus
from backloggd.models.library import UserLibrary
from backloggd.analytics.matcher import calculate_similarity_raw, compare_libraries


def test_user_library_filtering():
    lib = UserLibrary(username="tester")
    lib.add(GameEntry(slug="game-1", title="Game 1", rating=5.0, status=GameStatus.PLAYED))
    lib.add(GameEntry(slug="game-2", title="Game 2", rating=3.5, status=GameStatus.PLAYED))
    lib.add(GameEntry(slug="game-3", title="Game 3", rating=None, status=GameStatus.BACKLOG))

    assert len(lib) == 3
    assert len(lib.rated_games) == 2
    assert len(lib.unrated_games) == 1
    assert len(lib.filter(status=GameStatus.BACKLOG)) == 1
    assert len(lib.filter(min_rating=4.0)) == 1

    # Verify get_stats() directly on UserLibrary
    stats = lib.get_stats()
    assert stats.total_games == 3
    assert stats.rated_count == 2
    assert stats.unrated_count == 1
    assert stats.average_rating == 4.25
    assert stats.played_count == 2
    assert stats.backlog_count == 1
    assert stats.rating_distribution == {3.5: 1, 5.0: 1}



def test_identical_libraries_similarity():
    ratings1 = {"zelda": 5.0, "mario": 4.0, "metroid": 4.5}
    ratings2 = {"zelda": 5.0, "mario": 4.0, "metroid": 4.5}

    final_score, lib_score, rating_score = calculate_similarity_raw(ratings1, ratings2, k_shrinkage=0)
    assert lib_score == 100.0
    assert rating_score == 100.0
    assert final_score == 100.0


def test_recommendations_and_disagreements():
    lib1 = UserLibrary(username="u1")
    lib2 = UserLibrary(username="u2")

    lib1.add(GameEntry(slug="game-a", title="Game A", rating=5.0, status=GameStatus.PLAYED))
    lib1.add(GameEntry(slug="game-b", title="Game B", rating=1.0, status=GameStatus.PLAYED))

    lib2.add(GameEntry(slug="game-a", title="Game A", rating=5.0, status=GameStatus.PLAYED))
    lib2.add(GameEntry(slug="game-b", title="Game B", rating=5.0, status=GameStatus.PLAYED))
    lib2.add(GameEntry(slug="game-c", title="Game C", rating=4.5, status=GameStatus.PLAYED))

    comp = compare_libraries(lib1, lib2)

    # Mutual favorite
    assert any(g.slug == "game-a" for g in comp.mutual_favorites)

    # Big disagreement on game-b (5.0 vs 1.0)
    assert any(d.game.slug == "game-b" and d.difference == 4.0 for d in comp.disagreements)

    # Recommendations: game-c should be recommended to u1
    assert any(g.slug == "game-c" for g in comp.recommendations_for_user1)
