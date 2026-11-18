# Changelog

## 0.2.4

### Added
- `BackloggdClient.get_user_collection_counts()` reads Played, Playing, Backlog, and Wishlist totals from one Games page, including explicit zero counts.

## 0.2.3

### Added
- Grouped activity entries expose each named game through `grouped_games`.
- `BackloggdClient.get_user_game_rating()` reads the profile owner's score from a single game logs page, including games without play sessions.

## 0.2.2

### Fixed
- Journal pagination follows only forward links for the same journal.
- Both clients reject repeated journal pages before returning duplicate or incomplete history.

## 0.2.1

### Added
- Public synchronous and asynchronous activity snapshots with boundary IDs, page budgets, and explicit coverage reporting. Pages without validated pagination controls report unsupported coverage.

### Fixed
- Library statuses now describe the profile owner's selected collection instead of the signed-in viewer's hidden log data.
- Hidden viewer ratings no longer fill missing owner ratings. Viewer log IDs, dates, likes, and completion labels are not attributed to the owner.
- Old SDK library caches are invalidated so incorrect status data is refetched. Applications storing their own copies must refresh those separately.
- Regression coverage uses sanitized actual Backloggd collection HTML and public sync/async client APIs.
