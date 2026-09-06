"""The keep/cut rule.

Keep by default. Only three things are cut, and each has to be positively
identified:

1. the opponent's adventure-map turn -- clock overlay up, their digits ticking,
   Tieulinh's frozen;
2. a HotA lobby, menu or reconnect screen;
3. waiting while the opponent fights -- both clocks frozen, but Tieulinh's own
   screen still shows the adventure map.

The inverse rule ("cut whenever Tieulinh's clock is frozen") is the intuitive
one and it is wrong: combat, the tactics phase, the spell book, towns, hero
screens and level-up dialogs all freeze both clocks or hide the overlay, so it
throws away the fights. On the reference VOD that mistake cost 23:49 of real
gameplay.
"""
import numpy as np

from . import config as C


def runs_of(mask, t):
    """Contiguous True stretches of `mask` as [start, end] second pairs."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append([float(t[i]), float(t[j] + 1 / C.SR)])
            i = j + 1
        else:
            i += 1
    return out


def candidate_spans(t, widget, mine, theirs, min_len=4.0):
    """Stretches that the clocks cannot classify on their own.

    These are what passes 2 and 3 need to look at: no clock overlay at all, or
    both clocks frozen.
    """
    no_clock = [r for r in runs_of(~widget, t) if r[1] - r[0] >= min_len]
    both_frozen = [r for r in runs_of(widget & ~mine & ~theirs, t)
                   if r[1] - r[0] >= min_len]
    return sorted(no_clock + both_frozen), both_frozen


def within(segments, start, end):
    """The parts of `segments` that lie inside [start, end].

    Used to give one game its own segment list. A game boundary is the day
    counter resetting, and that happens without the players going through the
    lobby -- so there is usually no cut at the boundary and the segment
    spanning it has to be divided rather than handed to one side. Measured on
    one VOD, four of five boundaries landed 22 to 77 seconds inside a segment.

    A leftover shorter than MIN_KEEP is dropped rather than published as a
    two-second video at the start of a game.
    """
    out = []
    for a, b in segments:
        lo, hi = max(a, start), min(b, end)
        if hi - lo >= C.MIN_KEEP:
            out.append([lo, hi])
    return out


def build(t, widget, mine, theirs, dead_t, map_t, dur):
    """Return (segments, stats): the stretches to keep, and what was removed."""
    cut_opponent = widget & theirs & ~mine

    dead = np.zeros(len(t), bool)
    for ts in dead_t:                           # dead screens come at 1 s steps
        i0 = int(round(ts * C.SR))
        dead[i0:i0 + int(C.SR)] = True

    waiting = np.zeros(len(t), bool)
    for ts in map_t:
        i0 = int(round(ts * C.SR))
        waiting[i0:i0 + 1] = True
    waiting &= widget & ~mine & ~theirs

    cut = cut_opponent | dead | waiting

    # Bridge cut stretches too short to be worth a transition, then drop kept
    # fragments too short to be worth showing.
    merged = []
    for span in runs_of(~cut, t):
        if merged and span[0] - merged[-1][1] < C.MIN_CUT:
            merged[-1][1] = span[1]
        else:
            merged.append(span)

    padded = []
    for a, b in [s for s in merged if s[1] - s[0] >= C.MIN_KEEP]:
        a = max(0.0, a - C.PAD_PRE)
        b = min(dur, b + C.PAD_POST)
        if padded and a <= padded[-1][1]:
            padded[-1][1] = max(padded[-1][1], b)
        else:
            padded.append([a, b])

    # Every join costs the viewer about a second of fade and black, so a gap has
    # to be worth more than that. MIN_CUT above is measured before padding, and
    # padding then takes PAD_PRE + PAD_POST off each gap, so the real floor is
    # only 3.8 s -- short enough to fill the list with cuts that save less time
    # than the transition costs. Enforce the minimum on the final gaps instead.
    segments = []
    for span in padded:
        if segments and span[0] - segments[-1][1] < C.MIN_GAP:
            segments[-1][1] = span[1]
        else:
            segments.append(span)

    stats = {
        "opponent turns": cut_opponent.sum() / C.SR,
        "lobby/menu/reconnect": dead.sum() / C.SR,
        "waiting on opp combat": waiting.sum() / C.SR,
    }
    return segments, stats
