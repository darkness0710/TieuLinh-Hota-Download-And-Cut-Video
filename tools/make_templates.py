#!/usr/bin/env python
"""Rebuild the reference crops in templates/ from a VOD.

Only needed if a VOD uses a different overlay than the one in tlh/config.py.
Give it a timestamp where each screen is on show; the crop regions themselves
come from the config, so fix those first with `inspect_frames.py grid`.

    python tools/make_templates.py input/vod.mp4 \\
        --at tieulinh_name=2525 --at lobby_header=3060 \\
        --at lobby_buttons=6660 --at menu_options=5700 \\
        --at menu_logo=5700 --at reconnect_abort=4450

Each template is also written to templates/preview/<name>.png at 3x so you can
eyeball what was actually captured before trusting it.
"""
import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tlh import config as C          # noqa: E402
from tlh.ffmpeg import grab          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--at", action="append", default=[], metavar="NAME=SECONDS",
                    help="timestamp showing that screen; repeat per template")
    args = ap.parse_args()

    regions = dict(C.DEAD_REG)
    regions["tieulinh_name"] = C.TIEULINH_TPL
    times = {}
    for item in args.at:
        if "=" not in item:
            ap.error(f"--at wants NAME=SECONDS, got {item!r}")
        name, secs = item.split("=", 1)
        if name not in regions:
            ap.error(f"unknown template {name!r}; pick from {sorted(regions)}")
        times[name] = float(secs)
    if not times:
        ap.error("give at least one --at NAME=SECONDS")

    C.TEMPLATES.mkdir(exist_ok=True)
    preview = C.TEMPLATES / "preview"
    preview.mkdir(exist_ok=True)

    for name, t in sorted(times.items()):
        frame = grab(args.video, t)
        if frame is None:
            print(f"  {name:<16} FAILED: no frame at {t}s")
            continue
        y0, y1, x0, x1 = regions[name]
        crop = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[y0:y1, x0:x1]
        cv2.imwrite(str(C.TEMPLATES / f"{name}.png"), crop)
        cv2.imwrite(str(preview / f"{name}.png"),
                    cv2.resize(crop, None, fx=3, fy=3,
                               interpolation=cv2.INTER_NEAREST))
        print(f"  {name:<16} {crop.shape[1]}x{crop.shape[0]}  from {t:.1f}s")
    print(f"\nwrote to {C.TEMPLATES}, previews in {preview}")
    print("check the previews, then verify with: python run.py --dry-run")


if __name__ == "__main__":
    main()
