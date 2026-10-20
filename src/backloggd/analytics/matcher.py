"""Taste matching, rating agreements, and recommendation algorithms."""

import math
from typing import Optional
from backloggd.models.game import GameEntry
from backloggd.models.library import UserLibrary
from backloggd.models.comparison import MatchComparison, RatingDisagreement


def calculate_similarity_raw(
    ratings1: dict[str, Optional[float]],
    ratings2: dict[str, Optional[float]],
    k_shrinkage: int = 10,
) -> tuple[float, float, float]:
    """Calculate library overlap, rating agreement, and combined similarity score.

    Returns:
        tuple[float, float, float]: (final_score, library_score, rating_score)
    """
    if not ratings1 or not ratings2:
        return 0.0, 0.0, 0.0

    shared_slugs = ratings1.keys() & ratings2.keys()
    if not shared_slugs:
        return 0.0, 0.0, 0.0

    # 1. Library Overlap (Szymkiewicz-Simpson & Jaccard blend)
    total_unique = len(ratings1.keys() | ratings2.keys())
    jaccard = len(shared_slugs) / total_unique if total_unique > 0 else 0.0
    overlap_coeff = len(shared_slugs) / min(len(ratings1), len(ratings2))
    library_score = 0.5 * jaccard + 0.5 * overlap_coeff  # [0.0, 1.0]

    # 2. Rating Agreement on mutually rated games
    rated_pairs = [
        (ratings1[s], ratings2[s])
        for s in shared_slugs
        if ratings1[s] is not None and ratings2[s] is not None
    ]
    n_rated = len(rated_pairs)
    if n_rated == 0:
        return round(library_score * 100, 2), round(library_score * 100, 2), 0.0

    # Absolute agreement
    mae = sum(abs(r1 - r2) for r1, r2 in rated_pairs) / n_rated
    mae_sim = max(0.0, 1.0 - (mae / 4.5))

    # Pearson relative correlation
    mean1 = sum(r1 for r1, _ in rated_pairs) / n_rated
    mean2 = sum(r2 for _, r2 in rated_pairs) / n_rated
    diffs1 = [r1 - mean1 for r1, _ in rated_pairs]
    diffs2 = [r2 - mean2 for _, r2 in rated_pairs]
    mag1 = math.sqrt(sum(d * d for d in diffs1))
    mag2 = math.sqrt(sum(d * d for d in diffs2))

    if mag1 > 0 and mag2 > 0:
        pearson = sum(a * b for a, b in zip(diffs1, diffs2)) / (mag1 * mag2)
        pearson_sim = (pearson + 1.0) / 2.0
        raw_rating_sim = 0.5 * pearson_sim + 0.5 * mae_sim
    else:
        raw_rating_sim = mae_sim

    # Confidence shrinkage discount
    confidence = n_rated / (n_rated + k_shrinkage)
    rating_score = confidence * raw_rating_sim

    final_score = (0.30 * library_score + 0.70 * rating_score) * 100
    return (
        round(final_score, 2),
        round(library_score * 100, 2),
        round(rating_score * 100, 2),
    )


def compare_libraries(
    lib1: UserLibrary,
    lib2: UserLibrary,
    k_shrinkage: int = 10,
    recommendation_min_rating: float = 4.0,
) -> MatchComparison:
    """Perform full taste comparison between two user libraries."""
    ratings1 = lib1.to_ratings_dict()
    ratings2 = lib2.to_ratings_dict()

    final_score, lib_score, rate_score = calculate_similarity_raw(
        ratings1, ratings2, k_shrinkage=k_shrinkage
    )

    shared_slugs = lib1.slugs & lib2.slugs
    mutually_rated_slugs = [
        s for s in shared_slugs
        if ratings1[s] is not None and ratings2[s] is not None
    ]

    # Mutual Favorites (both rated >= 4.0)
    mutual_favorites: list[GameEntry] = []
    for s in mutually_rated_slugs:
        r1, r2 = ratings1[s], ratings2[s]
        if r1 is not None and r2 is not None and r1 >= 4.0 and r2 >= 4.0:
            mutual_favorites.append(lib1[s])
    mutual_favorites.sort(
        key=lambda g: ((ratings1[g.slug] or 0) + (ratings2[g.slug] or 0)),
        reverse=True,
    )

    # Disagreements (highest absolute rating difference)
    disagreements: list[RatingDisagreement] = []
    for s in mutually_rated_slugs:
        r1, r2 = ratings1[s], ratings2[s]
        if r1 is not None and r2 is not None:
            diff = abs(r1 - r2)
            if diff >= 1.5:  # Significant disagreement
                disagreements.append(
                    RatingDisagreement(
                        game=lib1[s],
                        user1_rating=r1,
                        user2_rating=r2,
                        difference=round(diff, 2),
                    )
                )
    disagreements.sort(key=lambda d: d.difference, reverse=True)

    # Recommendations: games User 2 loved (>= 4.0) that User 1 has not rated or logged
    recs_for_user1: list[GameEntry] = [
        g for g in lib2
        if g.rating is not None
        and g.rating >= recommendation_min_rating
        and (g.slug not in lib1 or not lib1[g.slug].is_rated)
    ]
    recs_for_user1.sort(key=lambda g: g.rating or 0, reverse=True)

    # Recommendations: games User 1 loved (>= 4.0) that User 2 has not rated or logged
    recs_for_user2: list[GameEntry] = [
        g for g in lib1
        if g.rating is not None
        and g.rating >= recommendation_min_rating
        and (g.slug not in lib2 or not lib2[g.slug].is_rated)
    ]
    recs_for_user2.sort(key=lambda g: g.rating or 0, reverse=True)

    return MatchComparison(
        user1=lib1.username,
        user2=lib2.username,
        similarity_score=final_score,
        library_score=lib_score,
        rating_score=rate_score,
        shared_games_count=len(shared_slugs),
        mutually_rated_count=len(mutually_rated_slugs),
        mutual_favorites=mutual_favorites,
        disagreements=disagreements,
        recommendations_for_user1=recs_for_user1,
        recommendations_for_user2=recs_for_user2,
    )
