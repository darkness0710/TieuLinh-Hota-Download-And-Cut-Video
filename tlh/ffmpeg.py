"""ffmpeg location, duration probing, and raw-frame helpers.

The ffmpeg binary comes from imageio-ffmpeg so there is nothing to install
separately and no PATH dependency.
"""
import subprocess

import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()


def hms(x):
    """Seconds -> h:mm:ss, clamped at zero."""
    x = max(0, x)
    return f"{int(x)//3600}:{int(x)%3600//60:02d}:{int(x)%60:02d}"


def duration(video):
    """Length in seconds, read from the container header.

    imageio-ffmpeg ships no ffprobe, so this parses `ffmpeg -i` output. The
    `-t 0.1` keeps it from decoding the whole file just to print a header.
    """
    # ffmpeg echoes the file's metadata, and these VOD titles are Vietnamese.
    # text=True alone decodes with the Windows codepage, which cannot represent
    # them: the reader thread dies, .stderr comes back None, and the caller
    # fails far away from the real cause.
    err = subprocess.run(
        [FF, "-hide_banner", "-t", "0.1", "-i", video, "-f", "null", "-"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace").stderr or ""
    for line in err.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"could not read duration of {video}")


def open_raw(video, start, dur, vf=None, filter_complex=None, size=None):
    """Start ffmpeg decoding `video` into raw bgr24 on stdout.

    Returns (process, frame_bytes). Caller reads frame_bytes at a time until a
    short read. `size` is (w, h) of the filtered output and is required so the
    caller knows the frame stride.
    """
    if (vf is None) == (filter_complex is None):
        raise ValueError("pass exactly one of vf / filter_complex")
    w, h = size
    cmd = [FF, "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", video]
    if vf is not None:
        cmd += ["-vf", vf]
    else:
        cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    frame_bytes = w * h * 3
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=frame_bytes * 8), frame_bytes


def frames(video, start, dur, size, vf=None, filter_complex=None):
    """Yield decoded frames as (h, w, 3) uint8 arrays."""
    w, h = size
    proc, fsz = open_raw(video, start, dur, vf=vf, filter_complex=filter_complex,
                         size=size)
    try:
        while True:
            buf = proc.stdout.read(fsz)
            if len(buf) < fsz:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def grab(video, t, size=(1920, 1080), vf=None):
    """Single frame at `t`, or None if the seek landed past the end.

    Uses ffmpeg rather than cv2.VideoCapture.set(): OpenCV's millisecond
    seeking drifts by tens of seconds on long H.264 files, which quietly
    corrupts anything built on it.
    """
    w, h = size
    if vf is None:
        vf = f"scale={w}:{h}" if size != (1920, 1080) else "null"
    raw = subprocess.run(
        [FF, "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
         "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True).stdout
    need = w * h * 3
    if len(raw) < need:
        return None
    return np.frombuffer(raw[:need], np.uint8).reshape(h, w, 3).copy()
