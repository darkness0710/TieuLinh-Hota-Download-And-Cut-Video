#!/usr/bin/env python
"""Entry point: trim every VOD in input/ into output/.

    python run.py                           # input/ -> output/
    python run.py --url https://youtu.be/X  # download into input/, then cut it
    python run.py --url ... --download-only # download only, cut nothing
    python run.py --urls links.txt          # a list of URLs, one per line
    python run.py --dry-run                 # analyse only, write segments.csv
    python run.py --parts-only              # render the pieces, do not join
    python run.py --per-game                # one video per game, not one per stream
    python run.py --only "abc*.mp4"         # files matching a glob (repeatable)
    python run.py --file "exact name.mp4"   # exactly this file (repeatable)
    python run.py -i D:\\vods -o D:\\cut

Given --url or --urls, only the downloaded files are processed; without them,
everything already sitting in input/ is.

Inputs keep the name they were downloaded under. Outputs are named after the
day the stream happened, taken from YouTube at download time:

    input/[Heroes 3] Live ngan... [U197AGXIO3s].mp4
      ->  output/[23-08-2026] Stream.mp4
          output/[23-08-2026] Stream.txt      (chapters)

A second stream from the same day becomes "(2)". A file already rendered is
skipped, so an interrupted batch can be restarted; one that fails is reported
and the batch carries on.
"""
import argparse
import fnmatch
import os
import sys
import time

from tlh import config as C, fetch, naming
from tlh.process import process_video

ROOT = os.path.dirname(os.path.abspath(__file__))



def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    ap.add_argument("-i", "--input", default=os.path.join(ROOT, "input"),
                    help="folder of VODs (default: input/)")
    ap.add_argument("-o", "--output", default=os.path.join(ROOT, "output"),
                    help="where the cuts go (default: output/)")
    ap.add_argument("-w", "--work", default=os.path.join(ROOT, "work"),
                    help="scratch root, one subfolder per video (default: work/)")
    ap.add_argument("--url", action="append", default=[], metavar="URL",
                    help="download this VOD into input/ first; repeatable")
    ap.add_argument("--urls", metavar="FILE",
                    help="text file of URLs, one per line (# comments allowed)")
    ap.add_argument("--only", action="append", default=[], metavar="GLOB",
                    help="process only files matching this glob; repeatable")
    ap.add_argument("--file", action="append", default=[], metavar="NAME",
                    help="process exactly this file name; repeatable. Needed "
                         "because downloaded names contain [brackets], which a "
                         "glob reads as a character class and never matches")
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel analysis processes (default 4)")
    ap.add_argument("--render-workers", type=int, default=3,
                    help="parallel hardware encoders (default 3). Measured: 6 "
                         "of them cost about 1 GB more RAM and finished 3%% "
                         "faster, because integrated graphics has one encode "
                         "engine to share")
    ap.add_argument("--dry-run", action="store_true",
                    help="analyse and write the segment list, do not render")
    ap.add_argument("--download-only", action="store_true",
                    help="fetch the VOD into input/ and stop: no analysis, "
                         "no cutting. Useful on a good connection now for a "
                         "run later, and for keeping the original")
    ap.add_argument("--parts-only", action="store_true",
                    help="render each kept stretch into work/<name>/parts and "
                         "stop there, without concatenating them into output/")
    ap.add_argument("--per-game", action="store_true",
                    help="one video per game -- '[DD-MM-YYYY] Opponent (game "
                         "N).mp4' -- instead of one video for the whole stream")
    ap.add_argument("--force", action="store_true",
                    help="re-render even if the output already exists")
    ap.add_argument("--reanalyse", action="store_true",
                    help="ignore the cached signal in work/ and decode again")
    ap.add_argument("--live-progress", action="store_true",
                    help="redraw one download progress line instead of many")
    ap.add_argument("--keep-parts", action="store_true",
                    help="do not delete work/<name>/parts after concatenating")
    args = ap.parse_args()
    # These runs take tens of minutes; a block-buffered stdout would show
    # nothing at all until the process exits. UTF-8 because VOD titles are
    # Vietnamese and the Windows console codepage cannot encode them -- without
    # this, printing a title raises UnicodeEncodeError and kills the batch.
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    # stderr too: yt-dlp's warnings quote the title, so a redirected run died
    # on the same UnicodeEncodeError from the other stream.
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not os.path.isdir(args.input):
        print(f"input folder not found: {args.input}")
        print("create it and drop the VODs in, or pass -i")
        return 1

    urls = list(args.url)
    if args.urls:
        with open(args.urls) as fh:
            urls += [ln.strip() for ln in fh
                     if ln.strip() and not ln.startswith("#")]
    fetched = []
    for n, url in enumerate(urls, 1):
        print(f"===== download [{n}/{len(urls)}] {url}")
        path = fetch.download(url, args.input, workroot=args.work,
                              live=args.live_progress)
        if path:
            fetched.append(os.path.basename(path))
        else:
            print("  skipping this URL\n")
    if urls:
        print()
    # Given URLs and not one of them arrived, stop. Falling through here runs
    # whatever happens to be in input/ instead -- which is how a link that
    # died at 87% turned into an hour spent analysing the silent video-only
    # leftover it had just left behind.
    if urls and not fetched:
        print("nothing downloaded, so there is nothing to cut.")
        print("input/ is a library, not a queue: it is not processed just "
              "because a link failed.")
        return 1

    if args.download_only:
        # Downloading is the whole job, so stop before input/ is even read.
        if not urls:
            print("--download-only needs --url or --urls: "
                  "there is nothing to download")
            return 2
        for name in fetched:
            path = os.path.join(args.input, name)
            print(f"  saved {path}   {os.path.getsize(path) / 2 ** 30:.2f} GiB")
        print(f"\n{len(fetched)} file(s) downloaded into {args.input}, "
              "nothing cut (--download-only)")
        return 0

    def wanted(name):
        if args.file and name in args.file:
            return True
        if args.only and any(fnmatch.fnmatch(name, g) for g in args.only):
            return True
        return not args.file and not args.only

    videos = sorted(
        os.path.join(args.input, f) for f in os.listdir(args.input)
        if f.lower().endswith(C.VIDEO_EXTS) and wanted(f))
    # Given URLs, process just those: input/ is a library, not a queue.
    if urls:
        videos = [v for v in videos if os.path.basename(v) in fetched]
    if not videos:
        picked = args.file + args.only
        where = args.input + (f" matching {picked}" if picked else "")
        print(f"no video files in {where}")
        return 1

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.work, exist_ok=True)
    print(f"{len(videos)} file(s) to process   {args.input} -> {args.output}\n")

    ok, skipped, failed = [], [], []
    batch_started = time.time()
    for n, video in enumerate(videos, 1):
        stem = os.path.splitext(os.path.basename(video))[0]
        workdir = os.path.join(args.work, naming.work_slug(stem))
        print(f"===== [{n}/{len(videos)}]")
        out, already = naming.output_name(video, args.output, args.work)
        # Neither a dry run nor a parts-only run writes the output, so an
        # existing one is not a reason to skip either of them.
        if (already and not args.force and not args.dry_run
                and not args.parts_only and not args.per_game
                and os.path.getsize(out) > 1 << 20):
            print(f"  already rendered as {os.path.basename(out)}, "
                  "skipping (use --force to redo)\n")
            skipped.append(video)
            continue
        started = time.time()
        try:
            rc = process_video(video, out, workdir,
                               workers=args.workers,
                               render_workers=args.render_workers,
                               dry_run=args.dry_run,
                               reuse_signal=not args.reanalyse,
                               keep_parts=args.keep_parts,
                               parts_only=args.parts_only,
                               per_game=args.per_game)
        except Exception as exc:                # keep the batch alive
            print(f"  ERROR {type(exc).__name__}: {exc}")
            rc = 1
        mins = (time.time() - started) / 60
        if rc == 0:
            print(f"  ok in {mins:.1f} min\n")
            ok.append((video, out, workdir))
        else:
            print(f"  FAILED rc={rc} after {mins:.1f} min\n")
            failed.append((video, rc))

    print("=" * 64)
    print(f"{len(ok)} ok, {len(skipped)} skipped, {len(failed)} failed"
          f"   in {(time.time()-batch_started)/60:.1f} min")
    for video, out, workdir in ok:
        print()
        print(f"  input     {video}")
        if args.parts_only:
            # Naming the output here would be a lie: parts-only writes none.
            print(f"  pieces    {os.path.join(workdir, 'parts')}")
            print(f"  chapters  {os.path.join(workdir, 'chapters.txt')}")
        elif args.per_game:
            # One name per game, already printed above as each one finished.
            print(f"  videos    {args.output}   (one per game, listed above)")
        elif not args.dry_run:
            print(f"  output    {out}")
            print(f"  chapters  {naming.chapters_path(out)}")
    for video, rc in failed:
        print(f"  FAILED rc={rc}  {video}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
