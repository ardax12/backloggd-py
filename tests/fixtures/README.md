# Backloggd HTML fixtures

`ardax12_journal.html` contains the real journal result section captured with
headed Chromium from https://backloggd.com/u/ardax12/journal/ on 2026-11-12.
Navigation, forms, scripts, and security-related metadata are excluded. The
original month headings, day containers, game rows, ratings, and log links
are preserved.

The key regression is within January 2026: A Way Out is on the 20th, Omori
on the 16th, and Catherine on the 5th. The upstream backwards traversal
incorrectly gives all three games the 20th.

The public individual log pages for `life-is-strange`, `omori`, and
`catherine` were also inspected. Their rendered markup exposes playthrough
sections but no stable per-session ID. Links of the form
`/u/ardax12/logs/<game>/` identify a user's game history, not a session.
This date correction deliberately preserves the upstream entry IDs; it does
not make those IDs suitable for deduplicating individual playthroughs.


`millers_activity.html` and `millers_journal.html` contain sanitized public
sections captured with headed Chromium from Millers' activity and journal
pages on 2026-11-12. The activity fixture includes the Vice City completion,
3-star rating, and exact UTC timestamp inside `data-tippy-content`. The
journal includes 30 rows, Started/Finished labels, and repeated same-day
Shovel Knight sessions. Action variants used by the rating/review/social
parser tests are synthetic modifications of the captured activity fixture;
they are not presented as additional observed website events.

## Profile owner collection statuses (2026-11-13)

The `*_games_*.html` fixtures are sanitized real library responses, not generated
status examples. `millers_games_played.html` and `millers_games_played_page2.html`
retain 70 distinct cards each, captured while authenticated as `ardax12`.
`barryquill_games_playing.html` contains three games, and
`barryquill_games_wishlist.html` contains two. The three other Millers collection
fixtures preserve real empty Playing, Backlog, and Wishlist pages.

The original `game-filters` collection attributes and selected owner tab are
preserved, together with the real game card wrappers, visible cover ratings,
cover classes, and hidden `preloaded-log-*` divs. Unrelated page navigation,
scripts, forms, quick-edit menus/buttons, event handlers, and tooltip HTML are
removed. No cookies, session tokens, or security challenge data are included.

The owner collection is identified by matching
`data-game-filters-base-url-value` (e.g. `/u/barryquill/games/playing/by/added/`)
and `data-game-filters-preset-value`. The preloaded logs and fade classes are
viewer-specific. In the Playing fixture, GTA IV, Counter-Strike 2, and Fortnite
all have the viewer's played/completed metadata despite being in the owner's
Playing collection. In Millers' Played fixture, Overwatch has no owner rating
but the viewer's hidden `data-rating="5"` previously leaked as 2.5 stars.

Tests that remove viewer metadata or deliberately conflict the collection
markers are explicit transformations of these captures, not claims about
additional observed website responses. The Playing/Wishlist/Played populated
captures and empty Backlog capture establish collection behavior without
fabricating a populated Backlog response.
