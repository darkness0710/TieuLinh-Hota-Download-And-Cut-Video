"""Encode each kept segment with its transition, then join them.

Each segment is encoded separately with a fade in, a fade out, and 0.4 s of
black appended by `tpad`/`apad`. Baking the black hold into the segment itself
means every file in the concat list comes out of the same encoder with the same
parameters, so the final join is a stream copy and cannot drift.

Cutting per segment is also faster than one filter pass over the whole VOD: a
segment only decodes its own range instead of the entire file.

Audio is faded alongside the video. Without `afade` every join pops, because
the cut lands mid-sentence in the streamer's commentary.
"""
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config as C
from . import encoder
from .ffmpeg import FF


def _one(job):
    video, i, a, b, is_last, outdir, codec, qflag = job
    dur = b - a
    out = os.path.join(outdir, f"seg{i:04d}.mp4")
    fade_out_at = max(0.0, dur - C.FADE)
    vf = (f"fade=t=in:st=0:d={C.FADE},"
          f"fade=t=out:st={fade_out_at:.3f}:d={C.FADE}")
    af = (f"afade=t=in:st=0:d={C.FADE},"
          f"afade=t=out:st={fade_out_at:.3f}:d={C.FADE}")
    if not is_last:
        vf += f",tpad=stop_mode=add:stop_duration={C.BLACK}:color=black"
        af += f",apad=pad_dur={C.BLACK}"
    # -r/-fps_mode are not optional: h264_qsv refuses to open when the frame
    # rate is not constant, and the filter chain leaves it unset.
    rc = subprocess.call(
        [FF, "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", video,
         "-vf", vf, "-af", af, "-c:v", codec]
        + encoder.quality_args(qflag)
        + ["-r", "60", "-fps_mode", "cfr",
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-y", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return i, rc


def run(video, segments, out, workers=3, outdir="parts", progress=print,
        keep_parts=False, parts_only=False):
    """Render `segments` of `video` into `out`. Returns an exit code.

    `parts_only` stops once the pieces are written, without concatenating
    them. When the question is what the detector decided, the pieces ARE the
    answer -- one file per kept stretch, watchable on their own -- and the
    finished file is a second copy of the same footage.
    """
    os.makedirs(outdir, exist_ok=True)
    codec, qflag = encoder.detect(log=progress)
    jobs = [(video, i, a, b, i == len(segments) - 1, outdir, codec, qflag)
            for i, (a, b) in enumerate(segments)]

    done, started, failed = 0, time.time(), []
    with ThreadPoolExecutor(workers) as pool:
        # as_completed, not map: map yields strictly in order, so one long
        # early segment holds back the count for every short one that has
        # already finished, and the progress line reports a third of the real
        # figure with a wildly pessimistic eta.
        futures = [pool.submit(_one, job) for job in jobs]
        for future in as_completed(futures):
            i, rc = future.result()
            done += 1
            if rc:
                failed.append(i)
                progress(f"    segment {i} failed rc={rc}")
            # Every fifth piece was a line every one to two minutes, which
            # left a progress bar reading 0% while nine of twenty-eight were
            # already rendered. One line per piece is only noise on a VOD with
            # a hundred of them.
            step = 1 if len(jobs) <= 40 else 5
            if done % step == 0 or done == len(jobs):
                el = time.time() - started
                progress(f"    {done}/{len(jobs)}  {el/60:.1f}min elapsed  "
                         f"eta {el/done*(len(jobs)-done)/60:.1f}min")

    if failed:
        progress(f"    {len(failed)} segment(s) failed, not concatenating: {failed}")
        return 1

    if parts_only:
        pieces = sorted(n for n in os.listdir(outdir) if n.endswith(".mp4"))
        size = sum(os.path.getsize(os.path.join(outdir, n)) for n in pieces)
        progress(f"    {len(pieces)} piece(s), {size/2**30:.2f} GiB, kept in "
                 f"{outdir}")
        progress("    parts only: not concatenating")
        return 0

    listing = os.path.join(outdir, "concat.txt")
    with open(listing, "w") as fh:
        for i in range(len(segments)):
            fh.write(f"file 'seg{i:04d}.mp4'\n")
    rc = subprocess.call(
        [FF, "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
         "-c", "copy", "-movflags", "+faststart", "-y", out])

    if rc == 0 and keep_parts is False:
        # The pieces are now a duplicate of the finished file -- for an eight
        # hour VOD that is several gigabytes sitting there for nothing. The
        # expensive thing to recompute is the signal, and that is cached
        # separately.
        freed = sum(os.path.getsize(os.path.join(outdir, n))
                    for n in os.listdir(outdir))
        shutil.rmtree(outdir, ignore_errors=True)
        progress(f"    cleaned up {freed/2**30:.2f} GiB of rendered pieces")
    return rc
