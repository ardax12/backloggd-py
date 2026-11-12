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
