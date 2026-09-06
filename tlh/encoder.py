"""Pick a working H.264 encoder for whatever machine this is running on.

`h264_qsv` was hardcoded while this was built, which only works on an Intel CPU
with QuickSync. On an AMD machine it fails, and on a machine with an NVIDIA card
it leaves a much faster encoder unused. Worse, the failure is a wall of ffmpeg
filter errors rather than "this machine has no QuickSync".

So the encoders are probed once, in order of how fast they usually are, by
actually encoding a couple of frames -- the only reliable test, since ffmpeg
lists encoders it cannot open. On this machine that measured: NVENC absent
(no NVIDIA hardware), AMF absent, QuickSync working.

The `-r`/`-fps_mode cfr` in the probe is not incidental: h264_qsv refuses to
open when the frame rate is not constant, which is exactly what a filter chain
leaves behind, so a probe without them would reject a perfectly good encoder.
"""
import json
import subprocess

from . import config as C
from .ffmpeg import FF

CACHE = C.ROOT / ".encoder.json"

# name -> the flag that sets quality for that encoder
CANDIDATES = [
    ("h264_nvenc", ["-cq"]),          # NVIDIA, usually the fastest
    ("h264_qsv", ["-global_quality"]),  # Intel QuickSync
    ("h264_amf", ["-qp_i"]),          # AMD
    ("libx264", ["-crf"]),            # software, always available
]


def _works(name):
    """Can this encoder actually open and produce output on this machine?"""
    cmd = [FF, "-hide_banner", "-v", "error",
           "-f", "lavfi", "-i", "testsrc=size=640x360:rate=60:duration=1",
           "-c:v", name, "-r", "60", "-fps_mode", "cfr",
           "-f", "null", "-"]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        return False
    # ffmpeg exits 0 even when the encoder failed to open, so check the text.
    bad = ("Could not open encoder", "Error while opening encoder",
           "Cannot load", "failed to open", "Unknown encoder")
    return not any(b in (done.stderr or "") for b in bad)


def detect(log=print, force=False):
    """(encoder_name, quality_flag). Cached, because probing costs seconds."""
    if not force and CACHE.exists():
        try:
            saved = json.loads(CACHE.read_text())
            return saved["name"], saved["flag"]
        except Exception:
            pass                                # unreadable cache: probe again

    for name, flag in CANDIDATES:
        if _works(name):
            if name == "libx264":
                log(f"        no hardware encoder found; falling back to "
                    f"{name} (roughly 3x slower)")
            else:
                log(f"        video encoder: {name}")
            CACHE.write_text(json.dumps({"name": name, "flag": flag[0]}))
            return name, flag[0]

    raise RuntimeError(
        "no usable H.264 encoder, not even libx264. The bundled ffmpeg is "
        "broken; reinstall with: pip install --force-reinstall imageio-ffmpeg")


def quality_args(flag):
    """Quality setting for the chosen encoder, aiming near the source bitrate."""
    # The scales differ per encoder: qsv global_quality and x264 crf are close
    # enough to share a number, nvenc cq is a little more aggressive.
    value = C.GQ if flag != "-cq" else C.GQ + 2
    return [flag, str(value)]
