# Changelog

## 0.2.1

### Added
- Public synchronous and asynchronous activity snapshots with boundary IDs, page budgets, and explicit coverage reporting. Pages without validated pagination controls report unsupported coverage.

### Fixed
- Library statuses now describe the profile owner's selected collection instead of the signed-in viewer's hidden log data.
- Hidden viewer ratings no longer fill missing owner ratings. Viewer log IDs, dates, likes, and completion labels are not attributed to the owner.
- Old SDK library caches are invalidated so incorrect status data is refetched. Applications storing their own copies must refresh those separately.
- Regression coverage uses sanitized actual Backloggd collection HTML and public sync/async client APIs.
