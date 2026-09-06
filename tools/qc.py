#!/usr/bin/env python
"""Check a cut before trusting it.

    cuts     contact sheet around the longest cuts: last frame kept, the middle
             of what was removed, first frame kept again. The middle tile should
             be an opponent turn or a lobby/menu, never a battle.
    fades    luma either side of each black hold in a rendered output, to prove
             the fade really reaches black and comes back
    labels   re-check hand-labelled timestamps against the segment list, so a
             change to the rule cannot quietly start cutting combat again

Examples
    python tools/qc.py cuts  input/vod.mp4 -s work/vod/segments.json
    python tools/qc.py fades output/vod_optimize.mp4 -s work/vod/segments.json
    python tools/qc.py labels -s work/vod/segments.json --labels labels.csv

labels.csv is `seconds,keep|cut,description` per line. The set built while
developing the rule for the reference VOD lives in tools/labels_reference.csv.
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tlh.ffmpeg import FF, grab, hms   # noqa: E402


def cmd_cuts(a):
    segs = json.load(open(a.segments))
    gaps = sorted(((segs[i][1], segs[i + 1][0]) for i in range(len(segs) - 1)),
                  key=lambda r: r[0] - r[1])[:a.count]
    w, h = 420, 236
    rows = []
    for start, end in gaps:
        tiles = []
        for tag, t, colour in (("KEPT last", start - 1.5, (0, 255, 255)),
                               ("CUT middle", (start + end) / 2, (80, 80, 255)),
                               ("KEPT next", end + 1.5, (0, 255, 255))):
            frame = grab(a.video, t, size=(w, h))
            if frame is None:
                frame = np.zeros((h, w, 3), np.uint8)
            cv2.rectangle(frame, (0, 0), (w - 1, 15), (0, 0, 0), -1)
            cv2.putText(frame, f"{tag} {hms(t)}", (3, 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1)
            tiles.append(frame)
        rows.append(np.hstack(tiles))
    if not rows:
        sys.exit("no cuts to show")
    cv2.imwrite(a.out, np.vstack(rows))
    print(f"wrote {a.out}  ({len(rows)} cuts)")
    print("the middle tile must never be a battle -- if it is, the rule is cutting combat")


def _luma(video, t):
    raw = subprocess.run(
        [FF, "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
         "-vf", "scale=96:54", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True).stdout
    if len(raw) < 96 * 54:
        return float("nan")
    return float(np.frombuffer(raw[:96 * 54], np.uint8).mean())


def cmd_fades(a):
    segs = json.load(open(a.segments))
    black = a.black
    joins, acc = [], 0.0
    for start, end in segs[:-1]:
        acc += (end - start) + black
        joins.append(acc - black / 2)
    bad = 0
    print(f"{len(joins)} join(s); checking the first {min(a.count, len(joins))}")
    for k, j in enumerate(joins[:a.count], 1):
        vals = [_luma(a.video, j + off) for off in (-3.0, 0.0, 3.0)]
        ok = vals[1] < 12 and vals[0] > 25 and vals[2] > 25
        bad += not ok
        print(f"  join {k:>3} @ {hms(j)}   before={vals[0]:6.1f} "
              f"black={vals[1]:5.1f} after={vals[2]:6.1f}   {'ok' if ok else 'CHECK'}")
    print(f"\n{len(joins[:a.count]) - bad}/{len(joins[:a.count])} joins look right")
    return 1 if bad else 0


def cmd_labels(a):
    segs = json.load(open(a.segments))

    def kept(t):
        return any(start <= t <= end for start, end in segs)

    rows = []
    with open(a.labels) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            secs, want, *rest = line.split(",")
            rows.append((float(secs), want.strip().lower(),
                         rest[0].strip() if rest else ""))
    bad = 0
    print(f"{'description':<38}{'time':>9}  got   want")
    for secs, want, desc in rows:
        got = "keep" if kept(secs) else "cut"
        mark = "" if got == want else "   <-- MISMATCH"
        bad += got != want
        print(f"{desc[:38]:<38}{hms(secs):>9}  {got:<6}{want}{mark}")
    print(f"\n{len(rows)-bad}/{len(rows)} correct")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("cuts"); p.add_argument("video")
    p.add_argument("-s", "--segments", default="segments.json")
    p.add_argument("-n", "--count", type=int, default=6)
    p.add_argument("-o", "--out", default="qc_cuts.png"); p.set_defaults(fn=cmd_cuts)

    p = sub.add_parser("fades"); p.add_argument("video", help="the RENDERED output")
    p.add_argument("-s", "--segments", default="segments.json")
    p.add_argument("-n", "--count", type=int, default=8)
    p.add_argument("--black", type=float, default=0.4); p.set_defaults(fn=cmd_fades)

    p = sub.add_parser("labels")
    p.add_argument("-s", "--segments", default="segments.json")
    p.add_argument("--labels", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "labels_reference.csv"))
    p.set_defaults(fn=cmd_labels)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
