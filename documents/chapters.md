# Chapters

The chapter list is written beside the video, sharing its name —
`output/[23-08-2026] Stream.txt` — and ready to paste into a YouTube
description. A copy stays in `work/<name>/chapters.txt`, which is also the only
copy a `--dry-run` or `--parts-only` run leaves, since neither writes an output
video:

```
00:00 Day 1 - Week 1 - Month 1 vs Opponent (game 1)
07:02 Day 2 - Week 1 - Month 1 vs Opponent (game 1)
33:39 Day 4 - Week 3 - Month 1 vs Opponent (game 1) - COMBAT
35:29 Day 1 - Week 1 - Month 1 vs Opponent (game 2)
```

Timestamps are on the **cut** timeline, not the source. Entries closer than ten
seconds are folded together, because YouTube rejects a list that packs them
tighter, and the first entry is pinned to 00:00 for the same reason.

## The day counter

Read from "Month: M, Week: W, Day: D" at the bottom right. It is on every
in-game screen and absent in the lobby, so its anchor doubles as an "are we in
a game" test.

Two measured details drive the reader: in combat and in a no-timer game the
whole bottom panel is **dimmed** (text peak 250 -> 228), so the strip is
binarised with Otsu rather than a fixed threshold; and in that variant the
leading "M" of "Month:" is clipped, so the anchor is "Week:", which survives
both.

## Games

Split where the day counter goes backwards. That is what a restart looks like —
the players re-roll the map and start again at day 1 — and it happens without
passing through the lobby, so a lobby-based split would miss it. Anything
shorter than two minutes is a re-roll rather than a game and gets no chapter.

## Battles

Marked only when they are hero against hero: a battle screen shows a "Spell
Points" panel per side, and two of them means a PvP fight while one means
neutral guards. Measured, this separates at 0.99 against 0.17 — far sharper
than judging a battle by the colour of the bottom bar, which cannot tell combat
from a tavern or an open spell book.

## Why players are not named

Reading a stylised game font well enough to print someone's name is the least
reliable thing that could go in this pipeline, and a misread is silent. Games
are numbered instead, and the number matters more than a name would: every game
restarts the day counter, so without it a dozen chapters would all read
"Day 1 - Week 1".
