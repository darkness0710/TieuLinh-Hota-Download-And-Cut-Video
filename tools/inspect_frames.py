#!/usr/bin/env python
"""Look at frames of a VOD, for working out coordinates or checking a hunch.

    probe     container info, plus whether the clock overlay is detectable
    grid      one frame with a labelled coordinate grid, for reading off pixels
    sheet     contact sheet of several timestamps side by side
    zoom      one region blown up, optionally across several timestamps
    clocks    filmstrip of just the two clock lines, to read them over time

Examples
    python tools/inspect_frames.py probe input/vod.mp4
    python tools/inspect_frames.py grid  input/vod.mp4 -t 3060 -o grid.png
    python tools/inspect_frames.py sheet input/vod.mp4 -t 3060,5700,5820,9880
    python tools/inspect_frames.py zoom  input/vod.mp4 -t 2600 -r 0,0,200,120 -f 5
    python tools/inspect_frames.py clocks input/vod.mp4 --from 2560 --to 2686 --step 6

Frames are pulled with ffmpeg, never cv2.VideoCapture.set(): OpenCV's
millisecond seeking drifts by tens of seconds on long H.264 files, which makes
any filmstrip built on it silently wrong.
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tlh import config as C            # noqa: E402
from tlh import signal                 # noqa: E402
from tlh.ffmpeg import duration, grab  # noqa: E402


def _stamp(img, text, colour=(0, 255, 255), scale=0.45):
    h = max(16, int(20 * scale / 0.45))
    cv2.rectangle(img, (0, 0), (img.shape[1] - 1, h), (0, 0, 0), -1)
    cv2.putText(img, text, (3, h - 4), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 1)
    return img


def hm(t):
    return f"{int(t)//3600}:{int(t)%3600//60:02d}:{int(t)%60:02d}"


def cmd_probe(a):
    dur = duration(a.video)
    print(f"{a.video}\n  duration {hm(dur)} ({dur:.1f}s)")
    frame = grab(a.video, min(60.0, dur / 2))
    if frame is None:
        print("  could not read a frame")
        return
    print(f"  frame {frame.shape[1]}x{frame.shape[0]}")
    cx, cy, cw, ch = C.CLK
    clk = frame[cy:cy + ch, cx:cx + cw].astype(np.int16)
    b, g, r = clk[:, :, 0], clk[:, :, 1], clk[:, :, 2]
    # Same measurement signal.py makes: ink per LINE, colour-agnostic, plus the
    # hue of each line so a wrong-looking result shows which colour is where.
    ink = np.maximum(b - (g + r) // 2, r - (g + b) // 2)
    hue = (r - (g + b) // 2) - (b - (g + r) // 2)
    up, lo = ink[C.UPPER_BAND], ink[C.LOWER_BAND]
    n_up, n_lo = int((up > 60).sum()), int((lo > 60).sum())
    c_up = signal._line_hue(hue[C.UPPER_BAND], up)
    c_lo = signal._line_hue(hue[C.LOWER_BAND], lo)
    ok = n_up > C.P_DIGIT and n_lo > C.P_DIGIT
    name = lambda c: "red" if c > 0 else ("blue" if c < 0 else "-")  # noqa: E731
    print(f"  clock digits at this sample: upper={n_up} ({name(c_up)}) "
          f"lower={n_lo} ({name(c_lo)})")
    print(f"  (need >{C.P_DIGIT} on both)  -> "
          f"{'detected' if ok else 'not detected'}")
    if not ok:
        print("  note: the overlay is hidden in combat/menus, so one sample "
              "proving nothing is normal. Try a few timestamps.")


def cmd_grid(a):
    frame = grab(a.video, a.t[0], size=(960, 540))
    if frame is None:
        sys.exit("no frame there")
    for x in range(0, 960, 80):
        cv2.line(frame, (x, 0), (x, 539), (0, 255, 255), 1)
        cv2.putText(frame, str(x * 2), (x + 2, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    for y in range(0, 540, 60):
        cv2.line(frame, (0, y), (959, y), (0, 255, 255), 1)
        cv2.putText(frame, str(y * 2), (2, y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    cv2.imwrite(a.out, frame)
    print(f"wrote {a.out}  (labels are full-res coords; image is half scale)")


def cmd_sheet(a):
    w, h = 420, 236
    tiles = []
    for t in a.t:
        frame = grab(a.video, t, size=(w, h))
        if frame is None:
            continue
        tiles.append(_stamp(frame, hm(t)))
    if not tiles:
        sys.exit("no frames read")
    cols = a.cols
    while len(tiles) % cols:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(a.out, np.vstack(rows))
    print(f"wrote {a.out}  ({len(a.t)} frames, {cols} per row)")


def cmd_zoom(a):
    x, y, w, h = [int(v) for v in a.region.split(",")]
    tiles = []
    for t in a.t:
        frame = grab(a.video, t)
        if frame is None:
            continue
        crop = cv2.resize(frame[y:y + h, x:x + w], None, fx=a.factor, fy=a.factor,
                          interpolation=cv2.INTER_NEAREST)
        tiles.append(_stamp(crop, hm(t)))
    if not tiles:
        sys.exit("no frames read")
    cv2.imwrite(a.out, np.vstack(tiles))
    print(f"wrote {a.out}  region x={x} y={y} w={w} h={h} at {a.factor}x")


def cmd_clocks(a):
    rows = []
    for t in range(a.start, a.end, a.step):
        frame = grab(a.video, t)
        if frame is None:
            continue
        crop = cv2.resize(frame[42:95, 30:120], None, fx=3, fy=3,
                          interpolation=cv2.INTER_NEAREST)
        label = np.zeros((crop.shape[0], 120, 3), np.uint8)
        cv2.putText(label, hm(t)[-5:], (4, crop.shape[0] // 2 + 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        rows.append(np.hstack([label, crop]))
    if not rows:
        sys.exit("no frames read")
    half = len(rows) // 2 + len(rows) % 2
    left, right = np.vstack(rows[:half]), np.vstack(rows[half:])
    if right.shape[0] < left.shape[0]:
        pad = np.zeros((left.shape[0] - right.shape[0], right.shape[1], 3), np.uint8)
        right = np.vstack([right, pad])
    gap = np.zeros((left.shape[0], 20, 3), np.uint8)
    cv2.imwrite(a.out, np.hstack([left, gap, right]))
    print(f"wrote {a.out}  ({len(rows)} samples, top line blue / bottom red)")


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def times(s):
        return [float(x) for x in s.split(",")]

    p = sub.add_parser("probe"); p.add_argument("video"); p.set_defaults(fn=cmd_probe)

    p = sub.add_parser("grid"); p.add_argument("video")
    p.add_argument("-t", type=times, required=True, help="one timestamp in seconds")
    p.add_argument("-o", "--out", default="grid.png"); p.set_defaults(fn=cmd_grid)

    p = sub.add_parser("sheet"); p.add_argument("video")
    p.add_argument("-t", type=times, required=True, help="comma-separated seconds")
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("-o", "--out", default="sheet.png"); p.set_defaults(fn=cmd_sheet)

    p = sub.add_parser("zoom"); p.add_argument("video")
    p.add_argument("-t", type=times, required=True)
    p.add_argument("-r", "--region", required=True, metavar="X,Y,W,H")
    p.add_argument("-f", "--factor", type=int, default=4)
    p.add_argument("-o", "--out", default="zoom.png"); p.set_defaults(fn=cmd_zoom)

    p = sub.add_parser("clocks"); p.add_argument("video")
    p.add_argument("--from", dest="start", type=int, required=True)
    p.add_argument("--to", dest="end", type=int, required=True)
    p.add_argument("--step", type=int, default=6)
    p.add_argument("-o", "--out", default="clocks.png"); p.set_defaults(fn=cmd_clocks)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
