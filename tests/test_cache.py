import tempfile
import time
from pathlib import Path
from backloggd.cache import CacheManager
from backloggd.models.game import GameEntry, GameStatus
from backloggd.models.library import UserLibrary


def test_cache_set_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(cache_path=db_path, ttl_seconds=3600)

        # 1. Miss
        assert cache.get("testuser") is None

        # 2. Add library
        lib = UserLibrary(username="testuser")
        lib.add(GameEntry(slug="zelda", title="Zelda", rating=5.0, status=GameStatus.PLAYED))
        cache.set(lib)

        # 3. Hit
        cached = cache.get("testuser")
        assert cached is not None
        assert cached.username == "testuser"
        assert len(cached) == 1
        assert cached["zelda"].rating == 5.0

        # 4. Invalidation
        cache.delete("testuser")
        assert cache.get("testuser") is None


def test_cache_expiration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(cache_path=db_path, ttl_seconds=0.05)

        lib = UserLibrary(username="quickuser")
        lib.add(GameEntry(slug="mario", title="Mario", rating=4.0, status=GameStatus.PLAYED))
        cache.set(lib)

        # Sleep past ttl
        time.sleep(0.06)
        assert cache.get("quickuser") is None
