"""Passes 2 and 3: recognise screens where nothing is being played.

The clocks alone cannot answer two questions:

* Whether a stretch with no clock overlay is real play or a lobby/menu. HotA
  hides the overlay during combat, town and hero screens and some dialogs, and
  some games are played with no timer at all -- so "no clock" is not idle time.
* Whether a stretch with BOTH clocks frozen is Tieulinh's own battle or
  Tieulinh waiting while the opponent fights. Combat freezes both clocks either
  way.

The first is settled by template-matching the handful of dead screens; the
second by the bottom bar, which is the blue resource strip on the adventure map
and a wooden status bar in combat.

Both passes only ever look at the candidate stretches pass 1 flagged, not the
whole video.
"""
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import cv2
import numpy as np

from . import config as C
from .ffmpeg import frames, hms

CHUNK = 120.0       # seconds of video per job, so jobs are comparable in size
HEARTBEAT = 15.0    # seconds between progress lines


def _chunks(spans, chunk=CHUNK):
    """Split spans into jobs of at most `chunk` seconds each.

    Candidate stretches range from a few seconds to twenty minutes. One job per
    stretch makes progress meaningless -- "3/50" says nothing about how much
    video is left -- and leaves the workers idle at the end while one long job
    finishes alone. Both chunk workers compute absolute timestamps from their
    own start, so splitting a stretch changes nothing about the result.
    """
    out = []
    for a, b in spans:
        x = a
        while x < b:
            y = min(b, x + chunk)
            out.append((x, y))
            x = y
    return out


def _sweep(video, spans, worker, workers, progress, label):
    """Run `worker` over `spans` in parallel, reporting real progress.

    Progress is counted in SECONDS OF VIDEO checked, not jobs finished, and
    printed on a heartbeat so a long stretch cannot look like a hang. Results
    are collected with as_completed rather than pool.map: map yields in
    submission order, so nothing at all prints until the first job finishes,
    however many workers have finished theirs.
    """
    jobs = _chunks(spans)
    total = sum(b - a for a, b in jobs) or 1.0
    rows, done, last = [], 0.0, 0.0
    with ProcessPoolExecutor(workers) as pool:
        pending = {pool.submit(worker, (video, a, b)): (a, b) for a, b in jobs}
        progress(f"    {label}   0%   0:00:00 of {hms(total)} to check")
        for future in as_completed(pending):
            a, b = pending[future]
            rows.extend(future.result())
            done += b - a
            now = time.time()
            if now - last >= HEARTBEAT or done >= total:
                last = now
                progress(f"    {label} {100 * done / total:3.0f}%   "
                         f"{hms(done)} of {hms(total)} checked")
    return rows


def _dead_chunk(job):
    """Best dead-screen template score per second over one stretch."""
    video, a, b = job
    tpl = {}
    for name in C.DEAD_REG:
        img = cv2.imread(str(C.TEMPLATES / f"{name}.png"), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(C.TEMPLATES / f"{name}.png")
        tpl[name] = img

    rows = []
    for i, frame in enumerate(frames(video, a, b - a, (1920, 1080), vf="fps=1")):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best = 0.0
        for name, (y0, y1, x0, x1) in C.DEAD_REG.items():
            pad = C.DEAD_PAD
            window = gray[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            score = float(cv2.matchTemplate(
                window, tpl[name], cv2.TM_CCOEFF_NORMED).max())
            if score > best:
                best = score
        rows.append((a + i, best))
    return rows


def dead_screens(video, spans, workers=4, progress=print):
    """Timestamps (1 s resolution) inside `spans` that show a dead screen."""
    if not spans:
        return np.zeros(0)
    rows = _sweep(video, spans, _dead_chunk, workers, progress, "screens")
    if not rows:
        return np.zeros(0)
    arr = np.array(rows, dtype=float)
    return arr[arr[:, 1] > C.THR_TPL][:, 0]


def _bar_chunk(job):
    """Bottom-bar blue-minus-red per sample over one stretch."""
    video, a, b = job
    x, y, w, h = C.BAR
    rows = []
    for i, frame in enumerate(frames(video, a, b - a, (w, h),
                                     vf=f"crop={w}:{h}:{x}:{y},fps={C.SR}")):
        f = frame.astype(np.int16)
        rows.append((a + i / C.SR, float(f[:, :, 0].mean() - f[:, :, 2].mean())))
    return rows


def map_showing(video, spans, workers=4, progress=print):
    """Timestamps inside `spans` where the adventure map is on screen.

    Used only where both clocks are frozen: the map being up means Tieulinh is
    not the one in the battle.
    """
    if not spans:
        return np.zeros(0)
    rows = _sweep(video, spans, _bar_chunk, workers, progress, "map vs combat")
    if not rows:
        return np.zeros(0)
    arr = np.array(rows, dtype=float)
    return arr[arr[:, 1] > C.THR_BAR][:, 0]
