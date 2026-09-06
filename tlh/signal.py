"""Pass 1: everything that can be read from one decode of the video.

Per sample it produces:

* whether each H2H clock's digits moved since the last sample -- a running
  clock means that player is on the move, a frozen one means they are not;
* which name slot holds "Tieulinh HOTA", which fixes the colour, because the
  HUD always seats the red player left and the blue player right;
* the "Month: M, Week: W, Day: D" counter;
* whether a hero panel with "Spell Points" is showing on each side -- two of
  them means a hero-vs-hero battle, one means a fight against neutrals.

Six small regions, cropped and stacked into one tiny frame before leaving
ffmpeg. Shipping full 1080p frames through the pipe was the original
bottleneck: 9.6 GB for a 2h48 VOD against 2.4 GB now.
"""
import time
import warnings
from concurrent.futures import (FIRST_COMPLETED, ProcessPoolExecutor,
                                wait)
from multiprocessing import Manager

import cv2
import numpy as np

from . import config as C
from . import daycount
from .ffmpeg import frames, hms

# Column layout of the array extract() returns.
# Clock columns are named for the LINE they came from -- up(per) and lo(wer) --
# because the colour on a given line is not fixed. c_up/c_lo carry each line's
# hue so interpret() can tell which line belongs to which player.
COLUMNS = ("t", "d_up", "d_lo", "n_up", "n_lo", "c_up", "c_lo",
           "m_left", "m_right", "month", "week", "day", "spell_l", "spell_r")
IDX = {name: i for i, name in enumerate(COLUMNS)}


def _line_hue(hue, ink, floor=60):
    """Mean red-minus-blue over one clock line's digit pixels.

    Averaged over the digits alone, not the whole band: the overlay is
    semi-transparent, so the map behind it would otherwise decide the answer.
    Returns 0.0 for a line with no digits, which reads as "no opinion".
    """
    lit = ink > floor
    return float(hue[lit].mean()) if lit.any() else 0.0


def _filter():
    """Build the filter graph and the size of its output frame."""
    cx, cy, cw, chh = C.CLK
    lx, ly, lw, lh = C.NAME_L
    rx, ry, rw, rh = C.NAME_R
    dx, dy, dw, dh = C.DAY
    slx, sly, slw, slh = C.SPELL_L
    srx, sry, srw, srh = C.SPELL_R

    # The source is yuv420p, so ffmpeg silently rounds an odd crop width or
    # offset down to even. Branches that get stacked back together then
    # disagree on width and vstack refuses the graph, at a filter that looks
    # unrelated to the crop that caused it. Fail loudly here instead.
    odd = {name: val for name, val in
           (("CLK", C.CLK), ("NAME_L", C.NAME_L), ("NAME_R", C.NAME_R),
            ("DAY", C.DAY), ("SPELL_L", C.SPELL_L), ("SPELL_R", C.SPELL_R))
           if any(v % 2 for v in val)}
    if odd:
        raise ValueError(
            "these config regions must have even x/y/w/h for a yuv420p source, "
            f"fix them in tlh/config.py: {odd}")

    w = lw + rw                                 # the widest row sets the frame
    graph = (
        f"[0:v]fps={C.SR},split=6[a][b][c][d][e][f];"
        f"[a]crop={cw}:{chh}:{cx}:{cy},pad={w}:{chh}:0:0:black[clk];"
        f"[b]crop={lw}:{lh}:{lx}:{ly}[nl];"
        f"[c]crop={rw}:{rh}:{rx}:{ry}[nr];"
        f"[nl][nr]hstack=inputs=2[nm];"
        f"[d]crop={dw}:{dh}:{dx}:{dy},pad={w}:{dh}:0:0:black[day];"
        f"[e]crop={slw}:{slh}:{slx}:{sly}[sl];"
        f"[f]crop={srw}:{srh}:{srx}:{sry}[sr];"
        f"[sl][sr]hstack=inputs=2,pad={w}:{slh}:0:0:black[sp];"
        f"[clk][nm]vstack=inputs=2[t1];"
        f"[t1][day]vstack=inputs=2[t2];"
        f"[t2][sp]vstack=inputs=2[v]")
    return graph, (w, chh + lh + dh + slh)


def _rows():
    """Row offsets of each stacked band in the composed frame."""
    ch, lh, dh, sh = C.CLK[3], C.NAME_L[3], C.DAY[3], C.SPELL_L[3]
    return {"clock": (0, ch), "names": (ch, ch + lh),
            "day": (ch + lh, ch + lh + dh),
            "spell": (ch + lh + dh, ch + lh + dh + sh)}


def _pyramid(tpl, height, width, scales):
    """A template at every scale of `scales` that still fits its window."""
    out = []
    for scale in scales:
        t = (tpl if scale == 1.0 else
             cv2.resize(tpl, None, fx=scale, fy=scale,
                        interpolation=cv2.INTER_AREA))
        if t.shape[0] <= height and t.shape[1] <= width:
            out.append(t)
    return out


def _best_match(window, pyramid):
    """Best normalised correlation any scale of `pyramid` reaches in `window`.

    Taking the maximum over scales rather than picking one: the right scale is
    a property of the VOD, but a VOD does not announce it, and a plate matched
    at the wrong size scores about as well as empty panelling -- which is how a
    whole stream came to be read with a defaulted seat. See C.NAME_SCALES.
    """
    best = -1.0
    for t in pyramid:
        if t.shape[0] > window.shape[0] or t.shape[1] > window.shape[1]:
            continue
        best = max(best, float(cv2.matchTemplate(
            window, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


def _chunk(job):
    """Signal rows for one time range. Runs in a worker process."""
    video, start, dur, seen, slot = job
    tpl_name = cv2.imread(str(C.TEMPLATES / "tieulinh_name.png"), cv2.IMREAD_GRAYSCALE)
    if tpl_name is None:
        raise FileNotFoundError(C.TEMPLATES / "tieulinh_name.png")
    tpl_spell = {}
    for side in ("left", "right"):
        img = cv2.imread(str(C.TEMPLATES / f"spell_{side}.png"), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(C.TEMPLATES / f"spell_{side}.png")
        tpl_spell[side] = img
    atlas = daycount.load_atlas()
    pyr_name = _pyramid(tpl_name, C.NAME_L[3], C.NAME_L[2], C.NAME_SCALES)
    # The narrower of the two spell windows, so one pyramid serves both.
    pyr_spell = {side: _pyramid(img, C.SPELL_L[3],
                                min(C.SPELL_L[2], C.SPELL_R[2]), C.SPELL_SCALES)
                 for side, img in tpl_spell.items()}

    graph, size = _filter()
    band = _rows()
    lw, slw = C.NAME_L[2], C.SPELL_L[2]
    dw = C.DAY[2]
    pre = 1.0 if start > 0 else 0.0             # overlap so the first diff is real
    every = int(C.SR * 5)                       # name-template cadence, in samples

    rows, prev, i = [], None, 0
    for frame in frames(video, start - pre, dur + pre, size, filter_complex=graph):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        y0, y1 = band["clock"]
        clock = frame[y0:y1].astype(np.int16)
        b, g, r = clock[:, :, 0], clock[:, :, 1], clock[:, :, 2]
        # "How blue is this pixel" / "how red", as a continuous score. A binary
        # colour mask flips borderline pixels every time the encoder emits a
        # keyframe, which reads as a ticking clock; scoring, then thresholding
        # the difference, ignores that.
        blueness = b - (g + r) // 2
        redness = r - (g + b) // 2
        # Digit ink, whatever colour the digits happen to be. Scoring only
        # blueness on the upper line and only redness on the lower one assumes
        # an order the game does not guarantee, and reads zero on BOTH lines
        # when the order is reversed -- which is a frozen clock as far as
        # everything downstream can tell.
        ink = np.maximum(blueness, redness)
        up, lo = ink[C.UPPER_BAND], ink[C.LOWER_BAND]
        # Signed hue per line, averaged over that line's digit pixels only:
        # positive is red, negative is blue. interpret() compares the two.
        hue = redness - blueness
        c_up = _line_hue(hue[C.UPPER_BAND], up)
        c_lo = _line_hue(hue[C.LOWER_BAND], lo)

        t = start - pre + i / C.SR
        d_up = d_lo = 0
        if prev is not None:
            d_up = int((np.abs(up - prev[0]) > 60).sum())
            d_lo = int((np.abs(lo - prev[1]) > 60).sum())
        n_up, n_lo = int((up > 60).sum()), int((lo > 60).sum())

        ny0, ny1 = band["names"]
        names = gray[ny0:ny1]
        m_left = m_right = -1.0
        if i % every == 0:
            m_left = _best_match(names[:, :lw], pyr_name)
            m_right = _best_match(names[:, lw:], pyr_name)

        dy0, dy1 = band["day"]
        month, week, day = daycount.read_strip(gray[dy0:dy1, :dw], atlas)

        sy0, sy1 = band["spell"]
        spell = gray[sy0:sy1]
        spell_l = _best_match(spell[:, :slw], pyr_spell["left"])
        spell_r = _best_match(spell[:, slw:slw + C.SPELL_R[2]],
                              pyr_spell["right"])

        if t >= start - 1e-6:
            rows.append((t, d_up, d_lo, n_up, n_lo, c_up, c_lo,
                         m_left, m_right,
                         -1 if month is None else month,
                         -1 if week is None else week,
                         -1 if day is None else day,
                         spell_l, spell_r))
        prev, i = (up, lo), i + 1
        # Report decoded seconds so the parent can show a true percentage.
        # Every 30 s of video, because each update is an IPC round trip. Each
        # worker owns its own key, so there is nothing to contend over and no
        # update can be lost the way a shared counter would lose one.
        if seen is not None and i % int(30 * C.SR) == 0:
            seen[slot] = i / C.SR
    return rows


HEARTBEAT = 15.0        # seconds between progress lines while chunks are in flight


def extract(video, dur, workers=4, progress=print):
    """Signal table for the whole video, one row per sample; see COLUMNS."""
    step = max(300.0, dur / max(1, workers * 2))
    started = time.time()
    # Workers report how much video they have decoded into a shared counter.
    # The obvious alternative -- assuming each in-flight chunk is half done --
    # claimed 25% after fifteen seconds and promised an eta of forty-five
    # seconds for a twelve minute pass. A number that wrong is worse than none.
    # A multiprocessing.Value cannot be handed to submit() -- it is only
    # shareable by inheritance -- so this is a Manager dict, one key per chunk.
    manager = Manager()
    seen = manager.dict()
    jobs = [(video, float(s), float(min(step, dur - s)), seen, k)
            for k, s in enumerate(np.arange(0, dur, step))]
    rows = []
    with ProcessPoolExecutor(workers) as pool:
        pending = {pool.submit(_chunk, job) for job in jobs}
        done, last_said = 0, -HEARTBEAT
        while pending:
            finished, pending = wait(pending, timeout=HEARTBEAT,
                                     return_when=FIRST_COMPLETED)
            for future in finished:
                rows.extend(future.result())
                done += 1
            elapsed = time.time() - started
            if elapsed - last_said >= HEARTBEAT or not pending:
                last_said = elapsed
                decoded = sum(seen.values()) if dur else 0
                pct = min(99, int(100 * decoded / dur)) if dur else 0
                eta = (elapsed / pct * (100 - pct)) if pct >= 3 else None
                tail = f"   eta {hms(eta)}" if eta else ""
                progress(f"    signal {pct:3d}%   {hms(elapsed)} elapsed{tail}")
    if not rows:
        raise RuntimeError(
            "the signal pass decoded no frames. The filter graph was most "
            "likely rejected; run one chunk on its own to see what ffmpeg "
            "says: python -c \"from tlh.signal import _chunk; "
            "_chunk((r'VIDEO', 0, 30, None, 0))\"")
    rows.sort(key=lambda r: r[0])
    return np.array(rows, dtype=float)


def _tick_regularity(diffs, threshold, half, per_second):
    """Fraction of one-second bins in a +/- half window that saw a change.

    This measures how *evenly* a clock changes, not how much. A clock ticking
    once a second changes in every bin; the map scrolling behind the
    semi-transparent overlay changes the digits' edge pixels in bursts, leaving
    bins untouched. Magnitude cannot separate the two -- measured, a frozen
    clock reached 48 changed pixels against a running one's 42 -- whereas this
    puts them at 0.50 and 1.00.

    A strided view over a padded copy touches the data once, where slicing per
    sample allocated one temporary each: twenty thousand for a three hour VOD.
    """
    over = np.pad(diffs >= threshold, half, mode="constant")
    windows = np.lib.stride_tricks.sliding_window_view(over, 2 * half + 1)
    bins = (2 * half + 1) // per_second
    if bins == 0:
        return windows.any(axis=1).astype(float)
    trimmed = windows[:, :bins * per_second]
    return trimmed.reshape(len(windows), bins, per_second).any(axis=2).mean(axis=1)


def _fill_short_gaps(mask, max_gap):
    """Close gaps of up to `max_gap` samples between True stretches.

    Interior gaps only: a gap is closed only when the mask is True on both
    sides of it, so the first and last True of every run stay exactly where
    they were. That is the property that makes this safe on the opponent's
    clock -- a cut can never reach past the last sample where their clock was
    genuinely ticking.
    """
    if max_gap <= 0:
        return mask
    out = mask.copy()
    lit = np.flatnonzero(mask)
    for a, b in zip(lit[:-1], lit[1:]):
        if 1 < b - a <= max_gap + 1:
            out[a + 1:b] = True
    return out


def interpret(sig):
    """Turn the raw signal into per-sample booleans.

    Returns (t, widget, seat, tieulinh_running, opponent_running) where seat is
    +1 for the right/blue seat and -1 for the left/red one.
    """
    col = lambda name: sig[:, IDX[name]]        # noqa: E731
    t = col("t")
    d_up, d_lo = col("d_up"), col("d_lo")
    n_up, n_lo = col("n_up"), col("n_lo")
    c_up, c_lo = col("c_up"), col("c_lo")
    m_left, m_right = col("m_left"), col("m_right")

    # Both lines must be present. Requiring only one false-positives on the
    # HotA lobby, whose blue table fills the upper band while the lower stays
    # empty. The overlay does sometimes show a single clock, and those samples
    # fall outside `widget` -- which keeps that footage rather than cutting it,
    # the safe direction.
    widget = (n_up > C.P_DIGIT) & (n_lo > C.P_DIGIT)

    seat = np.zeros(len(t), np.int8)
    checked = m_left >= 0
    seat[checked & (m_right > C.NAME_MATCH) & (m_right > m_left)] = 1
    seat[checked & (m_left > C.NAME_MATCH) & (m_left > m_right)] = -1
    last = 0                                    # hold the last known seat forward
    for i in range(len(seat)):
        if seat[i]:
            last = seat[i]
        elif last:
            seat[i] = last
    if (seat == 0).any():
        fallback = next((s for s in seat if s), 0)
        if not fallback:
            # Nothing in the whole stream named a seat. Picking one anyway is
            # a coin toss on which clock belongs to whom, and getting it wrong
            # cuts Tieulinh's own turns and keeps the opponent's -- the exact
            # opposite of the job. Say it out loud instead of guessing.
            warnings.warn(
                "no frame matched the name plate: the seat is unknown and "
                "every turn will be attributed to the right-hand seat. Check "
                "NAME_L/NAME_R and C.NAME_SCALES against this VOD.",
                RuntimeWarning, stacklevel=2)
            fallback = 1
        seat[seat == 0] = fallback

    # A clock counts as running if it changed in most one-second bins of a
    # small window. The window absorbs aliasing -- at 2 fps against a 1 Hz
    # clock, individual samples land inside the same second and look frozen
    # mid-turn -- and asking for regularity rather than magnitude rejects the
    # bursts the scrolling map produces behind the overlay.
    per = max(1, int(round(C.SR)))
    steady_up = _tick_regularity(d_up, C.THR_TICK, C.WIN, per)
    steady_lo = _tick_regularity(d_lo, C.THR_TICK, C.WIN, per)

    # Which line is Tieulinh's. The redder of the two lines belongs to the red
    # player, and the left seat is red, so a left-seated Tieulinh owns the
    # redder line. Comparing the two lines beats testing either against a fixed
    # threshold: it needs no absolute calibration and cannot be thrown off by a
    # stream whose colours are dimmer overall. Decided per sample, because the
    # seat -- and with it the colour -- changes between games in one stream.
    upper_is_red = c_up > c_lo
    mine_upper = np.where(seat < 0, upper_is_red, ~upper_is_red)
    mine = np.where(mine_upper, steady_up, steady_lo) >= C.THR_REGULAR
    theirs = np.where(mine_upper, steady_lo, steady_up) >= C.THR_REGULAR
    # A clock does not stop and start again inside two seconds: a short hole in
    # an otherwise steady run is the sampler blinking, not the clock stopping.
    # Both clocks, because the same aliasing hits both -- and see C.CLOCK_GAP
    # for why this fills holes rather than holding a state forward.
    gap = int(round(C.CLOCK_GAP * C.SR))
    mine = _fill_short_gaps(mine, gap)
    theirs = _fill_short_gaps(theirs, gap)
    return t, widget, seat, mine, theirs
