# Checking a cut

```
python tools/qc.py labels -s work/<name>/segments.json
python tools/qc.py cuts   input/<name>.mp4 -s work/<name>/segments.json
python tools/qc.py fades  output/<name>.mp4 -s work/<name>/segments.json
```

**labels** re-checks hand-labelled timestamps. There are two sets, and both
matter:

```
python tools/qc.py labels -s work/<name>/segments.json --labels tools/labels_reference.csv
python tools/qc.py labels -s work/<name>/segments.json --labels tools/labels_bulwark.csv
```

`labels_reference.csv` guards the combat-freezes-both-clocks lesson: if one of
its combat entries flips to `cut`, that bug is back. `labels_bulwark.csv`
guards the scrolling-map lesson from a second VOD: if its first two entries
flip to `keep`, the detector has gone back to judging a clock by how much its
pixels changed.

One VOD was not enough to catch either — the reference video passed 24/24 while
a whole class of opponent turn was being kept in the other. **Any change to the
rule or to a threshold in `config.py` should be run against both sets**, not
just against whatever VOD is at hand.

**cuts** renders a contact sheet showing, for each of the longest cuts, the last
frame kept, the middle of what was removed, and the first frame kept again. The
middle tile should always be an opponent turn or a lobby/menu. If it is ever a
battle, stop and fix the rule.

**fades** measures luma either side of each black hold in the rendered file.
Expect roughly 100+ before, under 12 in the hold, 100+ after.

Chapters are worth spot-checking too: read the day counter out of the *rendered*
file at a few chapter timestamps and confirm it matches the label. Nine were
checked this way on the reference VOD and all nine matched.

## Watching the pieces instead

`debug.cmd` renders each kept stretch as its own file in `work/<name>/parts/`
and stops before joining them. A wrong cut is then one file to open rather than
a timestamp to hunt for in a three-hour video — which is how `seg0001` of the
test clip was caught: 6.7 seconds of an opponent turn kept, from a clock whose
regularity score straddled `THR_REGULAR`. See `CLOCK_GAP` in `config.py`.

A 30-minute slice makes a good test subject. Cut one with a stream copy, so
there is no re-encode and no quality loss:

```
ffmpeg -i "input/<vod>.mp4" -t 1800 -c copy -movflags +faststart "input/[DD-MM-YYYY] test 30min.mp4"
```

Keep the `[DD-MM-YYYY]` prefix — `naming.py` reads the date from it — and leave
the `[videoid]` out, or `fetch.already_have()` will offer the slice up as a
finished download of that link.

## If a VOD uses a different overlay

`run.py` warns when the clock overlay is found in under 20% of samples, rather
than silently producing a bad cut. In that case:

1. `python tools/inspect_frames.py probe input/vod.mp4` — is the clock detected?
2. `python tools/inspect_frames.py grid input/vod.mp4 -t <seconds>` — read the
   real pixel coordinates off the labelled grid.
3. Update `tlh/config.py`. Nothing else hardcodes geometry.

   Keep every x/y/w/h **even**. The source is yuv420p, so ffmpeg quietly rounds
   an odd crop down, and the branches that get stacked back together then
   disagree on width and the whole filter graph is rejected. `tlh/signal.py`
   checks this up front and names the offending region rather than letting
   ffmpeg fail with a wall of filter errors.
4. `python tools/make_templates.py input/vod.mp4 --at ...` — rebuild the
   reference crops, then check `templates/preview/`.
5. `debug.cmd -NoRender` and sanity-check `segments.csv` before rendering.

## The panel does not sit in the same place on every VOD

Measured on `[LCPHoRAiE18]`, a February 2025 stream: its bottom panel sits
**8 px left** of where `DIGIT_X` was measured, which is enough to bring the
colon of `Week:` inside the digit window. A colon is not filtered out by
height — the box from its top dot to its bottom dot is as tall as a digit —
so the reader took it for the leading digit of the number, failed to match it,
and refused the whole field. That VOD read its day counter in **0.4%** of
samples against 91% on the reference, `games()` therefore saw no restart at
all, and a five-game stream came out as one four-hour "game 1".

So the number is taken to be the rightmost run of blobs that sit close
together, and the label falls off the left (`C.GLYPH_GAP`). A few pixels of
drift no longer matter.

### How that was checked without the reference VOD

Neither reference VOD was on the machine, but their geometry could be
reproduced: slide the `DAY` crop right and this VOD's digits move into the
windows, which is the old layout in real Heroes 3 pixels rather than a
synthetic one. Sweeping the offset over 40 frames:

| crop offset | old reader | new reader | frames that differ |
|---|---|---|---|
| +0 (this VOD as it is) | 0/40 | **36/40** | 36 |
| +6 | 33/40 | **36/40** | 3 |
| **+8 (the old geometry)** | **36/40** | **36/40** | **0** |

At +8 the old reader peaks at 36/40 — 90%, which is the 91% the reference VOD
measured, so that offset is the layout the windows were cut for. There the new
reader returns *the same answer on every one of the 40 frames*. Blobs are only
ever dropped from the left across a gap wider than any inside a number, so a
window holding nothing but the number cannot change.

Multi-digit numbers are the one case the gap rule could in principle spoil, and
it cannot here: week is 1-4 and day is 1-7, and the digit atlas holds no 0, 8
or 9, so a month of 10 or more was never readable in the first place.

## The name plate is not always the size the template was cut at

The seat decides which clock line is Tieulinh's, and getting it wrong does not
degrade the cut — it **inverts** it, cutting his own turns and keeping the
opponent's.

`[LCPHoRAiE18]` draws the name plate **25% larger** than the VOD
`tieulinh_name.png` was cut from. Matched at one scale it topped out at 0.45,
under `NAME_MATCH`, at every one of thirteen points sampled across the stream.
So no sample ever named a seat, they all fell through to the default, and the
default is the right-hand seat — while this stream has Tieulinh on the left for
most of its five games.

Measured, per six-minute window, against the same windows read with the seat
the frame actually shows:

| window | seat | cut, defaulted | cut, measured | same footage |
|---|---|---|---|---|
| 0:45, 1:10, 1:30 | right | 5.3 / 40.7 / 29.4% | identical | **100%** |
| 0:20 | left | 14.9% | 26.1% | **0%** |
| 2:10 | left | 11.9% | 25.1% | **0%** |
| 2:40 | left | 49.0% | 45.0% | **0%** |
| 4:00 | left | 1.7% | 30.3% | **0%** |
| 4:20 | left | 50.6% | 46.2% | **0%** |
| 4:30 | left | 38.4% | 25.9% | **0%** |

Read the last column, not the two before it. At 2:40 the old code cut 49% and
the new cuts 45% — almost the same *quantity*, and not one second of it the
same *footage*. Turns alternate roughly half and half, so cutting the wrong
half looks identical in a summary line and is the opposite video.

The fix searches `C.NAME_SCALES` and takes the best, which finds the plate at
whatever size a stream draws it: the same thirteen points now read 0.88 in the
occupied slot against 0.42-0.51 in the empty one, and 13/13 name a seat. Scale
1.00 is in the list, so a VOD that already matched still matches at least as
well.

`interpret()` now warns when no frame in a whole stream named a seat, rather
than defaulting silently. That failure is worth a line of output: it is the
difference between a video of Tieulinh playing and a video of him waiting.

Still unchecked: `screens.py` matches its dead-screen templates at one scale
too. Those are drawn by the game rather than by the duel overlay, and the day
counter — also game-drawn — needed no rescaling on this VOD, so they are
probably unaffected. Probably is not measured.

## …and neither is the combat panel

Same VOD, next template along. `[LCPHoRAiE18]` came out with a chapter list of
nothing but day changes: `pvp_battles()` found zero fights in ninety minutes.

This one was **not** a scale problem, and measuring said so: rescaling the
template from 0.40 to 1.85 never got the score over 0.53, against a threshold
of 0.70. The first reading of the signal made it look hopeless — non-combat
samples reached 0.48, combat 0.52, no room between them.

That reading was wrong, because the ground truth was wrong. "Both clocks
stopped" is not combat: it is combat *or* a town *or* a hero screen *or* the
HotA lobby, which is the whole reason `pvp_battles()` looks at the spell
panels instead of the clocks. Sampling frames from the both-frozen stretches
and *looking at them* — one was the lobby host list — gave real labels, and
with those:

| method | combat, worst | not combat, best | gap |
|---|---|---|---|
| grey, one scale (as shipped) | 0.42 | 0.29 | separates, thinly |
| grey, over scales | **0.52** | **0.29** | **0.23** |
| Sobel gradient | 0.52 | 0.25 | 0.27 |
| Otsu binarised | 0.43 | 0.31 | 0.11 |

So the match was never meaningless — `THR_SPELL = 0.70` simply sat above
*both* clusters. Over 32 minutes of the clip the answer is the same three
battles at every threshold from **0.50 down to 0.30**, and none at 0.55 or
0.70. A plateau that wide is a mis-set constant, not a fragile heuristic, so
0.42 sits in the middle of it. Searching scales stays as well: it is what
lifts combat from 0.42 to 0.52 and doubles the margin.

Verified through the production path, not a reimplementation: `signal._chunk`
over 78:00-82:00 now records 115 and 133 samples above threshold on the two
panels and `pvp_battles()` returns 79:59-80:56, the siege that a frame from
the middle of it shows on screen. Before: nothing.

Worth keeping in mind about blast radius: nothing in the keep/cut rule reads
the spell columns. `segments.build()` takes the clocks, the dead screens and
the map test, and not this. Getting it wrong costs chapter labels, which is
why a threshold measured on one VOD is an acceptable risk here and would not
have been in `interpret()`.

