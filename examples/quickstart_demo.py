"""Quickstart demonstration script for backloggd-py.

Run this script to verify your setup, cookies, and SDK methods:
    python examples/quickstart_demo.py
"""

import sys
import time
from backloggd import Backloggd, GameStatus


def test_sync_sdk(cache_enabled: bool = False):
    status_str = "ENABLED" if cache_enabled else "DISABLED (Direct Network Requests)"
    print("=" * 65)
    print(f" TESTING SYNCHRONOUS CLIENT (`Backloggd`) - CACHE: {status_str}")
    print("=" * 65)

    total_start = time.perf_counter()

    with Backloggd(cache_enabled=cache_enabled) as client:
        # A. User Profile (Fast Profile-Only Fetch ~300ms)
        username = "ardax12"
        print(f"\n[+] Fetching user profile: {username} (profile-only)...")
        t0 = time.perf_counter()
        profile = client.get_user_profile(username, force_refresh=not cache_enabled)
        t_profile = time.perf_counter() - t0
        print(f"    - Avatar URL: {profile.avatar_url}")
        print(f"    - Bio: {profile.bio[:50]}..." if profile.bio else "    - Bio: None")
        print(f"    - Short URL: {profile.short_url}")
        print(f"    - Badges: {profile.badges}")
        print(f"    - Pinned Favorites: {[g.title for g in profile.favorite_games]}")
        print(f"    - Header counts: {profile.played_count} played, {profile.playing_count} playing, {profile.backlog_count} backlog")
        print(f"    - Time taken: {t_profile:.3f}s")

        # B. User Library (Dedicated Paginated Fetch)
        print(f"\n[+] Fetching user library: {username} (page 1)...")
        t0 = time.perf_counter()
        library = client.get_user_library(username, max_pages=1, force_refresh=not cache_enabled)
        t_user = time.perf_counter() - t0
        stats = library.get_stats()
        print(f"    - Games in Library: {len(library)} (rated: {stats.rated_count}, avg: {stats.average_rating}*)")
        print(f"    - Time taken: {t_user:.3f}s")

        # C. Targeted Collections (Playing)
        print(f"\n[+] Fetching currently playing games: {username}...")
        t0 = time.perf_counter()
        playing_games = client.get_user_playing(username)
        t_playing = time.perf_counter() - t0
        print(f"    - Playing ({len(playing_games)} games): {[g.title for g in playing_games]}")
        print(f"    - Time taken: {t_playing:.3f}s")

        # D. Library Filtering & Export
        sample_dict = library.to_dict()[:1]
        print(f"    - Sample dict format: {sample_dict[0]['title']}")

        # E. Game Search
        query = "Hollow Knight"
        print(f"\n[+] Searching games: '{query}'...")
        t0 = time.perf_counter()
        search_results = client.search_games(query)
        t_search = time.perf_counter() - t0
        print(f"    - Found {len(search_results)} search results in {t_search:.3f}s")
        if search_results:
            top = search_results[0]
            print(f"    - Top Result: {top.title} ({top.release_year}) -> slug: '{top.slug}' [{top.game_type or 'Game'}]")

        # F. Individual Game Metadata
        game_slug = search_results[0].slug if search_results else "hollow-knight"
        print(f"\n[+] Fetching game metadata: {game_slug}...")
        t0 = time.perf_counter()
        game = client.get_game(game_slug, force_refresh=not cache_enabled)
        t_game = time.perf_counter() - t0
        print(f"    - Title: {game.title} ({game.release_year}) - Rating: {game.community_rating}*")
        print(f"    - Plays: {game.stats.plays_count} | Backlogs: {game.stats.backlogs_count}")
        print(f"    - Time taken: {t_game:.3f}s")

        # G. User Written Reviews
        print(f"\n[+] Fetching user reviews: {username} (page 1)...")
        t0 = time.perf_counter()
        reviews = client.get_user_reviews(username, max_pages=1)
        t_revs = time.perf_counter() - t0
        print(f"    - Found {len(reviews)} reviews")
        if reviews:
            top_rev = reviews[0]
            print(f"    - Latest: [{top_rev.rating}*] {top_rev.game_title} ({top_rev.like_count} likes)")
        print(f"    - Time taken: {t_revs:.3f}s")

        # H. User Custom Lists
        print(f"\n[+] Fetching user lists: {username}...")
        t0 = time.perf_counter()
        lists = client.get_user_lists(username)
        t_lists = time.perf_counter() - t0
        print(f"    - Found {len(lists)} lists")
        t_single_list = 0.0
        if lists:
            first_summary = lists[0]
            t0 = time.perf_counter()
            detailed_list = client.get_list(first_summary.url, force_refresh=not cache_enabled)
            t_single_list = time.perf_counter() - t0
            print(f"    - List loaded: '{detailed_list.title}' ({len(detailed_list.games)} games)")
            print(f"    - List fetch time: {t_single_list:.3f}s")
        print(f"    - Lists overview time: {t_lists:.3f}s")

        # I. Taste Comparison Engine
        user2 = "nehir"
        print(f"\n[+] Comparing taste: {username} vs {user2} (1 page each)...")
        t0 = time.perf_counter()
        comp = client.compare_users(username, user2, max_pages=1, force_refresh=not cache_enabled)
        t_comp = time.perf_counter() - t0
        print(f"    - Similarity Score: {comp.similarity_score}%")
        print(f"    - Mutual Favorites: {[g.title for g in comp.mutual_favorites[:2]]}")
        print(f"    - Recommendations: {[g.title for g in comp.recommendations_for_user1[:2]]}")
        print(f"    - Time taken: {t_comp:.3f}s")

    total_time = time.perf_counter() - total_start
    print("\n" + "-" * 65)
    print(f" SUMMARY - TOTAL TIME ({status_str}): {total_time:.4f}s")
    print(f"   * get_user_profile(fast):   {t_profile:.4f}s")
    print(f"   * get_user_library(p1):     {t_user:.4f}s")
    print(f"   * get_user_playing:         {t_playing:.4f}s")
    print(f"   * search_games:             {t_search:.4f}s")
    print(f"   * get_game:                 {t_game:.4f}s")
    print(f"   * get_user_reviews(1 page): {t_revs:.4f}s")
    print(f"   * get_user_lists:           {t_lists:.4f}s")
    print(f"   * get_list(contents):       {t_single_list:.4f}s")
    print(f"   * compare_users:            {t_comp:.4f}s")
    print("-" * 65)


def main():
    try:
        # Run 1: Direct Network (No Cache)
        test_sync_sdk(cache_enabled=False)

        # Run 2: Cached (SQLite)
        print("\n\n")
        test_sync_sdk(cache_enabled=True)

        print("\n" + "=" * 65)
        print(" ALL BENCHMARK TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 65)
    except Exception as e:
        print(f"\n[ERROR] An error occurred while testing SDK: {e}", file=sys.stderr)
        raise e


if __name__ == "__main__":
    main()
