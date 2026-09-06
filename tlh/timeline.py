"""Turn the signal into YouTube chapters for the cut video.

Chapters are anchored on three things read out of the frame:

* the "Month: M, Week: W, Day: D" counter, which is trusted only where a value
  holds for several samples AND follows legally from the one before it;
* game boundaries -- the counter resetting to day 1, which is what a restart
  looks like;
* hero-vs-hero battles, which show a "Spell Points" panel on BOTH sides. One
  panel means a fight against neutral guards and is not marked.

Two details this has to get right or the output is unusable. Times are on the
CUT timeline, not the source: a chapter pointing into removed footage is worse
than no chapter. And YouTube rejects a chapter list whose entries are less than
ten seconds apart, so anything closer is folded into the one before it.
"""
import numpy as np

from . import config as C
from . import daycount
from .signal import IDX

MIN_GAME = 120.0        # a "game" shorter than this is a map re-roll, not a game
MIN_CHAPTER_GAP = 10.0  # YouTube refuses chapters closer together than this
VOTE_MIN = 3            # samples a day value needs before it is believed


def _runs(values, times):
    """Consecutive equal values as (value, start, end)."""
    out, i = [], 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        out.append((values[i], float(times[i]), float(times[j])))
        i = j + 1
    return out


def day_runs(sig):
    """Stable (month, week, day) stretches, with misreads filtered out.

    Two filters, because they catch different mistakes:

    * a value has to hold for VOTE_MIN consecutive samples. A one-frame misread
      leaves a run of length 1, which is dropped, and the two halves of the real
      run either side of it are then merged back together.
    * a value has to be a legal successor of the one before it. Heroes 3 runs
      seven days to a week and never goes back, except at a restart -- which
      resets to day 1 and is recognised as such. A misread that happens to last
      a second and a half survives the first filter and is caught here.
    """
    t = sig[:, IDX["t"]]
    triples = [tuple(int(v) for v in row)
               for row in sig[:, [IDX["month"], IDX["week"], IDX["day"]]]]

    out = []
    for value, start, end in _runs(triples, t):
        if -1 in value:                     # a field the reader would not guess
            continue
        span = end - start
        if span * C.SR + 1 < VOTE_MIN:      # too brief to be a real day change
            continue
        out.append((value, start, end))

    # Merge neighbours reporting the same value across a short unreadable gap
    merged = []
    for value, start, end in out:
        if merged and merged[-1][0] == value:
            merged[-1][2] = end
        else:
            merged.append([value, start, end])

    # Drop anything the game could not actually have shown next. A restart is a
    # legal jump back to day 1, so it is kept and games() splits on it.
    kept = []
    for value, start, end in merged:
        previous = kept[-1][0] if kept else None
        restart = value[2] == 1 and value[1] == 1
        if previous is None or restart or daycount.plausible(previous, value):
            kept.append([value, start, end])
        elif kept:
            kept[-1][2] = end               # absorb the bad reading's time
    return [(tuple(v), s, e) for v, s, e in kept]


def games(runs, sig):
    """Split day runs into games. Returns [(start, end, [run, ...]), ...].

    A game ends when the day counter goes backwards. That is what a restart
    looks like -- the players re-roll the map and begin again at day 1 -- and it
    happens without passing through the lobby, so a lobby-based split misses it.

    Known limit: a game abandoned ON day 1 and immediately restarted never steps
    backwards, so those two count as one game. Splitting on the HUD name slot as
    well was tried and made it worse -- the 16-bit fingerprint of that slot
    flickers between adjacent samples and tore single games into ten. Doing it
    properly needs a tolerant, time-smoothed comparison, not an equality test.
    """
    if not runs:
        return []
    out, current = [], [runs[0]]
    for prev, cur in zip(runs, runs[1:]):
        if cur[0] < prev[0]:                    # (month, week, day) went back
            out.append(current)
            current = [cur]
        else:
            current.append(cur)
    out.append(current)
    return [(g[0][1], g[-1][2], g) for g in out]


def counter_gap(sig, start, end):
    """Longest stretch inside [start, end] with no readable day counter.

    A game span runs from its first day run to its last, so everything
    between them counts as inside it -- including a switch to a different
    game, if the counter picks up legally again afterwards. Splitting on the
    absence of a counter would be wrong (combat, towns and hero screens are
    real play), but the counter IS on every Heroes screen, combat included,
    so a long gap means whatever was on screen was not Heroes at all.

    Measured on a whole-Heroes VOD where the counter read in 91% of samples,
    the longest gap inside a game was one second -- so a threshold of minutes
    has a wide margin.
    """
    t = sig[:, IDX["t"]]
    inside = (t >= start) & (t <= end)
    readable = ~np.any(
        sig[:, [IDX["month"], IDX["week"], IDX["day"]]] == -1, axis=1)
    worst = run = 0.0
    for good in readable[inside]:
        if good:
            worst, run = max(worst, run), 0.0
        else:
            run += 1.0 / C.SR
    return max(worst, run)


def pvp_battles(sig, min_len=8.0, join_gap=60.0):
    """Stretches showing a hero panel on both sides, as (start, end).

    Runs closer together than `join_gap` are one battle: the panels blink out
    for a moment when a dialog opens mid-fight, and marking that as two
    separate battles puts two chapters half a minute apart.
    """
    t = sig[:, IDX["t"]]
    both = ((sig[:, IDX["spell_l"]] > C.THR_SPELL) &
            (sig[:, IDX["spell_r"]] > C.THR_SPELL))
    runs, i = [], 0
    while i < len(both):
        if both[i]:
            j = i
            while j + 1 < len(both) and both[j + 1]:
                j += 1
            runs.append([float(t[i]), float(t[j])])
            i = j + 1
        else:
            i += 1
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] <= join_gap:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    return [(a, b) for a, b in merged if b - a >= min_len]


def to_output_time(segments):
    """Map a source timestamp to its position in the cut video, or None."""
    spans, acc = [], 0.0
    for a, b in segments:
        spans.append((a, b, acc))
        acc += (b - a) + C.BLACK
    def convert(src):
        for a, b, offset in spans:
            if a <= src <= b:
                return offset + (src - a)
        return None
    return convert


OPPONENT = "Opponent"   # the players are not identified by name; see README
COMBAT = "COMBAT"


def played_games(sig):
    """Games worth counting: (number, source_start, source_end, day_runs).

    Anything shorter than MIN_GAME is a map re-roll rather than a game. Both
    the chapter labels and, when the stream is split into one video per game,
    the filenames come from this one list -- so "game 3" cannot mean different
    things in the two places.
    """
    played = [g for g in games(day_runs(sig), sig) if g[1] - g[0] >= MIN_GAME]
    return [(n, start, end, g_runs)
            for n, (start, end, g_runs) in enumerate(played, 1)]


def build(sig, segments):
    """Chapter list [(output_seconds, label), ...] for the cut video.

    `segments` decides the timeline this is measured against, so passing the
    segments of one game returns that game's chapters, rebased to its own
    00:00: every mark outside those segments converts to None and drops out.
    """
    convert = to_output_time(segments)
    battles = pvp_battles(sig)

    marks = []                                  # (source_time, label)
    for number, g_start, g_end, g_runs in played_games(sig):
        # Every game restarts the day counter, so without a number the list
        # reads as a dozen chapters all called "Day 1 - Week 1".
        tail = f" vs {OPPONENT} (game {number})"
        for (month, week, day), start, _end in g_runs:
            marks.append((start, f"Day {day} - Week {week} - Month {month}{tail}"))
        for b_start, _b_end in battles:
            if g_start <= b_start <= g_end:
                value = next((v for v, s, e in g_runs if s <= b_start <= e), None)
                head = (COMBAT if not value else
                        f"Day {value[2]} - Week {value[1]} - Month {value[0]}")
                marks.append((b_start, f"{head}{tail} - {COMBAT}"))

    chapters = []
    for src, label in sorted(marks):
        out = convert(src)
        if out is None:                         # this moment was cut away
            continue
        chapters.append((out, label))
    chapters.sort()

    # YouTube needs the list to start at zero and to space entries out. When two
    # marks fall too close, merging beats discarding: a battle that starts a
    # couple of seconds after a day rolls over was being dropped outright, which
    # threw away the one chapter a viewer actually wants.
    kept = []
    for out, label in chapters:
        if kept and out - kept[-1][0] < MIN_CHAPTER_GAP:
            previous_time, previous_label = kept[-1]
            if COMBAT in label and COMBAT not in previous_label:
                kept[-1] = (previous_time, f"{previous_label} - {COMBAT}")
            continue
        kept.append((out, label))
    if kept and kept[0][0] > 0:
        kept[0] = (0.0, kept[0][1])
    return kept


def write_youtube(chapters, path):
    """Write the description-ready chapter list."""
    with open(path, "w", encoding="utf-8") as fh:
        for out, label in chapters:
            mm, ss = divmod(int(out), 60)
            hh, mm = divmod(mm, 60)
            stamp = f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
            fh.write(f"{stamp} {label}\n")
    return path
