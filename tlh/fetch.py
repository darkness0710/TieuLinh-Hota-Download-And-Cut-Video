"""Download a VOD from a URL into input/, ready for the normal pipeline.

The detector reads fixed pixel coordinates out of a 1920x1080 frame, so the
format choice is not cosmetic: a 720p download would put every overlay in the
wrong place and produce a confidently wrong cut. This asks for 1080p H.264 plus
AAC, and refuses anything that does not come back at 1920x1080 rather than
handing the pipeline a file it will silently misread.
"""
import collections
import os
import re
import shutil
import subprocess
import threading
import time

from . import aria2, jsruntime
from .ffmpeg import FF

# Match the reference VOD: H.264 video and AAC audio in mp4, capped at 1080p.
# Falling back to any 1080p stream is fine; the resolution check below is what
# actually protects the pipeline.
FORMAT = ("bv*[height<=1080][vcodec^=avc1]+ba[acodec^=mp4a]/"
          "bv*[height<=1080]+ba/b[height<=1080]")

# How many stream slices to pull at once. googlevideo serves ONE connection at
# about 1 MiB/s -- near twice playback rate, and dead steady, so it is a cap
# and not congestion -- but the cap is per connection: measured with plain
# range requests, 1 connection gave 0.97 MiB/s, 8 gave 7.67, and 16 gave 11.5,
# which is the line itself.
#
# Four, not eight, because every fragment is a NEW connection -- about 600 of
# them for one VOD, one a second at full speed -- and at eight a home line
# started refusing to open them a few gigabytes in: "[WinError 10060] A
# connection attempt failed", SYNs going unanswered rather than refused, which
# is what a CGNAT session limit or an anti-abuse filter looks like. Four still
# runs at roughly 4 MiB/s (a 6 GiB VOD in half an hour) with half the churn.
# On a connection that can take it, eight or sixteen is faster.
PARALLEL = 4

# aria2c holds this many connections for the whole download instead of
# opening one per fragment. Eight measured 2.0 MiB/s on this line at a time
# when yt-dlp's fragments were down to 0.67; sixteen opened all sixteen and
# transferred nothing, which is the same wall the fragment churn hits.
ARIA2_CONNECTIONS = 8

# A download is restarted this many times before it is called a failure.
# Measured: an audio stream that had run for an hour died with every one of
# its eight connections reporting "unreachable host" in the same second --
# a route that went away, not a server that said no. aria2c's own retries
# cannot help there, and it says so itself as it gives up: "aria2 will resume
# download if the transfer is restarted." Everything already on disk is kept,
# and the restart also re-signs the googlevideo URLs, which the old ones
# would need anyway once they expire.
ATTEMPTS = 3
RETRY_WAIT = 30.0               # seconds, long enough for a route to come back


def _safe(name, limit=70):
    """A filename that survives Windows paths and the _optimize suffix."""
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return name[:limit].rstrip(" ._") or "video"


def probe_size(path):
    """(width, height) of a media file, or None."""
    # utf-8 explicitly: the banner carries the Vietnamese title, and the
    # Windows codepage cannot decode it. See tlh/ffmpeg.py duration().
    err = subprocess.run([FF, "-hide_banner", "-t", "0.1", "-i", path, "-f", "null", "-"],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr or ""
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", err)
    return (int(m.group(1)), int(m.group(2))) if m else None


# yt-dlp leaves these behind for a download it can pick up again.
PARTIAL_SUFFIXES = (".part", ".ytdl", ".temp", ".aria2")
# A fragmented download (see PARALLEL) also leaves "...f299.mp4.part-Frag12"
# lying around, which ends in none of the suffixes above. already_have() would
# then hand that 10 MiB fragment back as a finished video and the pipeline
# would sit down to cut it.
PARTIAL_FRAGMENT = re.compile(r"\.part-Frag\d+$", re.IGNORECASE)
# One stream of a pair, downloaded whole and waiting to be merged with the
# other: "...[LCPHoRAiE18].f299.mp4", video with no audio. It ends in .mp4 and
# carries no marker at all, so everything that looks for a video found one --
# already_have() handed it back as a finished download and skipped the audio
# for good, run.py picked it out of input/ and sat down to cut it, and the web
# page offered it with a Run button. Measured on the leftovers of a real
# failure: 7.33 GiB of silent video, called finished by all three.
PARTIAL_FORMAT = re.compile(r"\.f\d+\.[^.]+$", re.IGNORECASE)


def is_partial(name):
    """Is this one of yt-dlp's leftovers rather than a finished download?"""
    return (name.endswith(PARTIAL_SUFFIXES)
            or bool(PARTIAL_FRAGMENT.search(name))
            or bool(PARTIAL_FORMAT.search(name)))


def already_have(dest, video_id):
    """Path of a FINISHED download of this id, if any.

    Half-finished files carry the video id too, so matching on the id alone
    reports an interrupted download as a complete one. That short-circuits
    download() before yt-dlp is ever called, and the transfer neither resumes
    nor restarts -- it just silently does nothing. Skip the leftovers and let
    yt-dlp see the .part file, which is what it resumes from.
    """
    if not video_id or not os.path.isdir(dest):
        return None
    for name in os.listdir(dest):
        if f"[{video_id}]" not in name:
            continue
        if is_partial(name):
            continue
        return os.path.join(dest, name)
    return None


def partial_bytes(dest, video_id):
    """How much of an interrupted download is already on disk."""
    if not video_id or not os.path.isdir(dest):
        return 0
    total = 0
    for name in os.listdir(dest):
        if f"[{video_id}]" in name and is_partial(name):
            total += os.path.getsize(os.path.join(dest, name))
    return total


def download(url, dest, log=print, workroot=None, live=False):
    """Fetch `url` into `dest`. Returns the file path, or None on failure.

    `workroot` is where the download record goes, so the stream date is
    still known later when the file is processed by name alone.
    """
    try:
        import yt_dlp
    except ImportError:
        log("  yt-dlp is not installed. pip install -r requirements.txt")
        return None

    os.makedirs(dest, exist_ok=True)
    # Warnings are deliberately NOT suppressed here. They used to be, as
    # noise, and the paragraph about a missing JavaScript runtime that this
    # hid was the one warning that mattered: without a runtime the download
    # still works, fifty times slower. tlh/jsruntime.py has the measurements.
    # The n-parameter is solved during extraction, so the runtime has to be
    # passed to every YoutubeDL that reads formats, not just the downloader.
    deno = jsruntime.find()
    fast = aria2.find()
    probe = {"quiet": True, "skip_download": True, **_js_opts(deno)}
    with yt_dlp.YoutubeDL(probe) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as exc:
            first = str(exc).strip().splitlines()[0]
            log(f"  could not read this link: {first}")
            return None

    if info.get("is_live"):
        log("  this stream is still live; wait until it ends and the VOD is published")
        return None

    vid = info.get("id", "")
    existing = already_have(dest, vid)
    if existing:
        log(f"  already downloaded: {os.path.basename(existing)}")
        return existing

    # Lead with the stream date. The output name is built from that date, and
    # keeping it in the filename means it travels with the file: work/index.json
    # can be cleared, or the video copied to another machine, and the date is
    # still there to read. Falling back to the file's timestamp is a guess that
    # goes wrong as soon as a file has been copied.
    from . import naming
    date = naming.date_from_info(info)
    prefix = f"[{date}] " if date else ""
    stem = f"{prefix}{_safe(info.get('title', vid), limit=60)} [{vid}]"
    target = os.path.join(dest, stem + ".%(ext)s")
    dur = info.get("duration") or 0
    streams = _planned_streams(url, info, deno)
    sizes = [s["size"] for s in streams]
    # None, not a partial sum, when YouTube will not say: the free-space check
    # below has to know the difference between "small" and "unknown".
    need = sum(sizes) if streams and all(sizes) else None

    resume = partial_bytes(dest, vid)

    log("")
    log(f"  Title       {info.get('title', url)}")
    log(f"  Duration    {_hms(dur)}")
    log(f"  Size        {_gib(need) if need else 'unknown'}")
    if len(streams) > 1:
        log("  Streams     " + ", then ".join(
            f'{s["kind"]} {s["id"]}.{s["ext"]} {_size(s["size"])}' for s in streams))
    log(f"  Saving to   {os.path.abspath(dest)}")
    if resume:
        log(f"  Resuming    {_gib(resume)} already downloaded, continuing from there")
    free = shutil.disk_usage(os.path.abspath(dest)).free
    log(f"  Free space  {_gib(free)}")
    if need:
        # yt-dlp writes video and audio as separate .part files and then muxes
        # them into a third, so the peak is about twice the finished size.
        peak = need * 2
        if free < peak:
            log("")
            log(f"  NOT ENOUGH SPACE. Downloading needs about {_gib(peak)} free "
                f"while merging, and there is {_gib(free)}.")
            return None
        if free < peak * 2:
            log(f"  (tight: cutting this file afterwards needs roughly "
                f"{_gib(need)} more)")
    if deno:
        log(f"  JS runtime   deno at {deno}")
    else:
        # Loud, and above the progress bar rather than buried in a log: the
        # symptom otherwise looks like a healthy download that never ends.
        log("")
        log("  WARNING  no JavaScript runtime (deno) found.")
        log(f"           {jsruntime.WHY}")
        log("           Expect hours, not minutes. Stop this and fix it with:")
        log(f"             {jsruntime.INSTALL_HINT}")
    if fast:
        log(f"  Downloader   aria2c, {ARIA2_CONNECTIONS} held connections")
    else:
        log(f"  Downloader   yt-dlp, {PARALLEL} fragments at once")
        log(f"               aria2c is faster here: {aria2.INSTALL_HINT}")
    log("")

    started = time.time()
    # aria2c prints a progress readout of its own, and two bars fighting for
    # one line is worse than either, so ours stands down when it is driving.
    progress = _Progress(log, live=live and not fast, size_hint=need or 0)
    opts = {
        "format": FORMAT,
        "merge_output_format": "mp4",
        # yt-dlp downloads video and audio as separate streams and needs ffmpeg
        # to mux them. It only looks on PATH, and this project deliberately does
        # not install a system ffmpeg -- it uses the one inside imageio-ffmpeg.
        # Without this line the download runs to completion and then aborts with
        # "ffmpeg is not installed".
        "ffmpeg_location": FF,
        "outtmpl": target,
        "quiet": True,
        # YouTube also publishes these streams through m3u8, and those entries
        # can win the format selector on tbr and then fail to download
        # ("Unable to download format 312. Skipping...") -- after which the
        # selector falls quietly through to a vp9 stream, which is not what
        # this pipeline asked for.
        "extractor_args": {"youtube": {"skip": ["hls"]}},
        "retries": 20,
        # Fifteen seconds, because this is also how long a worker waits on a
        # connection that will never open, and once this line starts dropping
        # SYNs (WinError 10060) that wait is where the download goes: measured
        # mid-download, four workers managed 0.50 MiB/s between them while a
        # brand new connection got 0.96 on its own. A stream arriving at
        # ~1 MiB/s never falls 15 seconds silent, so nothing healthy is cut
        # off. With no timeout at all a dead connection is waited on forever:
        # no bytes, no error, no retry.
        "socket_timeout": 15,
        "progress_hooks": [progress.hook],
        "postprocessor_hooks": [progress.pp_hook],
        **_js_opts(deno),
    }
    if fast:
        opts.update({
            "external_downloader": {"default": fast},
            # yt-dlp hands aria2c -x16 -j16 -s16 of its own, and sixteen is
            # the setting that opened every connection here and then moved
            # nothing at all. These are appended after yt-dlp's, and aria2c
            # takes the last occurrence of a repeated option -- checked, not
            # assumed: -x1 after -x16 opens exactly one connection.
            "external_downloader_args": {"aria2c": [
                f"-x{ARIA2_CONNECTIONS}", f"-j{ARIA2_CONNECTIONS}",
                f"-s{ARIA2_CONNECTIONS}",
                "--max-tries=20", "--retry-wait=5",
                "--connect-timeout=15", "--timeout=15",
            ]},
            # false means "show it": aria2c's readout is the progress display
            # now, and yt-dlp gates it on this flag.
            "noprogress": False,
        })
    else:
        opts.update({
            # Our own bar owns this line; yt-dlp's fragment progress would
            # fight it for the same row, the two formats flickering back and
            # forth. The progress hooks still fire either way.
            "noprogress": True,
            # Without aria2c, the only way to hold more than one 1 MiB/s slot
            # is yt-dlp's fragment pool: `formats=dashy` asks the extractor
            # for the DASH-shaped view of the SAME stream -- same bytes, same
            # 5.97 GiB -- whose fragments are range requests, fetched several
            # at a time. It works. It also opens a connection per fragment,
            # which is the churn aria2c exists here to avoid.
            "extractor_args": {"youtube": {"formats": ["dashy"], "skip": ["hls"]}},
            "concurrent_fragment_downloads": PARALLEL,
            "fragment_retries": 20,
            # yt-dlp's default is to SKIP a fragment it could not fetch and
            # carry on. These fragments are byte ranges of one continuous mp4,
            # appended in order, so a skipped one does not leave a gap in the
            # video: every byte after it lands at the wrong offset and the file
            # is broken from there to the end, while still arriving looking
            # complete. Better to stop and say so -- the fragments already on
            # disk are kept, so running it again picks up from there.
            "skip_unavailable_fragments": False,
            # Only reached if a stream comes back unfragmented anyway. At
            # yt-dlp's 10 MiB default such a transfer arrives in 10 MiB bursts
            # with 20-60 seconds of silence between them; asked for in one
            # piece it runs continuously instead.
            "http_chunk_size": 100 * 2 ** 20,
        })
    try:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                break
            except Exception as exc:
                if attempt == ATTEMPTS:
                    log(f"  download failed after {attempt} attempts: {exc}")
                    return None
                log(f"  attempt {attempt} failed: {exc}")
                log(f"  waiting {RETRY_WAIT:.0f}s, then resuming from what is "
                    f"already on disk")
                time.sleep(RETRY_WAIT)
    finally:
        progress.close()

    path = already_have(dest, vid)
    if not path:
        log("  download reported success but no file appeared")
        return None

    if workroot:
        from . import naming
        naming.record_download(workroot, os.path.basename(path), info)

    size = probe_size(path)
    if size and size != (1920, 1080):
        log(f"  WARNING: got {size[0]}x{size[1]}, not 1920x1080. Every overlay "
            "coordinate in tlh/config.py assumes 1080p, so the cut would be "
            "wrong. Delete this file and fetch a 1080p version, or re-derive "
            "the coordinates with tools/inspect_frames.py grid.")
    log("")
    log(f"  Downloaded  {path}")
    log(f"  File size   {_gib(os.path.getsize(path))}")
    if started is not None:
        log(f"  Took        {_hms(time.time() - started)}")
    return path


def _hms(seconds):
    seconds = int(seconds or 0)
    return f"{seconds//3600}:{seconds%3600//60:02d}:{seconds%60:02d}"


def _gib(nbytes):
    return f"{nbytes / 2**30:.2f} GiB"


def _js_opts(deno):
    """Point yt-dlp at the deno we found, if we found one.

    Left out when there is none, so yt-dlp searches PATH itself and prints
    its own warning rather than being told about a runtime that is not there.
    """
    return {"js_runtimes": {"deno": {"path": deno}}} if deno else {}


def _planned_streams(url, info, deno=None):
    """What yt-dlp will actually fetch, in order, with sizes.

    YouTube keeps video and audio apart, so this is normally two downloads,
    and saying so up front matters: otherwise a 5.97 GiB video finishes and
    a 194 MiB audio file starts, which to anyone watching the bar looks like
    the merge going wrong.
    """
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                "format": FORMAT, **_js_opts(deno)}
        with yt_dlp.YoutubeDL(opts) as ydl:
            picked = ydl.process_ie_result(info, download=False)
    except Exception:
        return []
    plan = []
    for part in (picked.get("requested_formats") or [picked]):
        plan.append({
            "kind": "video" if (part.get("vcodec") or "none") != "none" else "audio",
            "id": part.get("format_id") or "?",
            "ext": part.get("ext") or "?",
            "size": part.get("filesize") or part.get("filesize_approx"),
        })
    return plan


def _size(nbytes):
    """GiB once it is worth it, MiB below that: 194 MiB reads better."""
    if not nbytes:
        return "?"
    return _gib(nbytes) if nbytes >= 2 ** 30 else f"{nbytes / 2**20:.0f} MiB"


class _Progress:
    """Download progress: many lines, or one line that redraws.

    The one-line form is drawn by a thread of its own instead of straight
    from the progress hook. The hook runs only when bytes arrive, so a
    throttled or half-dead connection leaves the last line frozen on screen
    -- showing the speed of a burst that ended a minute ago, and an ETA
    computed from it. That reads as "hung" when the truth is "waiting", and
    it hid a download running at 1/50 speed for long enough to matter. The
    thread redraws once a second whatever happens, and says how long the
    silence has lasted.

    Speed is averaged over a trailing window rather than taken from yt-dlp's
    per-chunk figure, for the same reason: an honest 0.2 MiB/s beats a
    momentary 11 MiB/s that no longer exists.
    """

    STALL_AFTER = 4.0     # seconds of silence before the line says so
    FRAG_STALL_AFTER = 30.0
    WINDOW = 20.0         # seconds of history the average speed covers

    def __init__(self, log, live=False, size_hint=0):
        self.log = log
        self.live = live
        self.lock = threading.Lock()
        self.samples = collections.deque()      # (clock, bytes downloaded)
        self.gaps = collections.deque(maxlen=8)  # seconds between updates
        self.frags = 0
        self.size_hint = size_hint or 0
        self.got = 0
        self.total = 0
        self.frac = 0.0
        self.name = None                        # video first, then audio
        self.last_data = time.time()
        self.active = False
        self.closed = False
        self.step = -1                          # last decade printed, non-live
        if live:
            threading.Thread(target=self._tick, daemon=True).start()

    def hook(self, d):
        if d["status"] != "downloading":
            if d["status"] == "finished":
                with self.lock:
                    self.active = False
                    self._clear()
                # yt-dlp's own summary line and aria2c's readout both
                # end in a carriage return, so without this the next
                # thing printed lands on top of them -- which is how
                # "Merging video and audio..." ended up sharing a row
                # with "[download] 100% of 5.97GiB".
                self.log("")
            return
        got = d.get("downloaded_bytes", 0)
        done = d.get("fragment_index") or 0
        frags = d.get("fragment_count") or 0
        if d.get("total_bytes"):
            total = d["total_bytes"]             # one plain request: exact
        else:
            # Fragments are equal slices of time, so this settles within a few
            # of them; before the first one lands there is only yt-dlp's own
            # estimate, which was seen wandering from 5.99 to 7.17 GiB.
            if done and frags and got:
                total = int(got * frags / done)
            else:
                total = d.get("total_bytes_estimate") or 0
            # Either way, the extractor already told us the exact size. It
            # covers video and audio together, so use it only for a stream it
            # plausibly describes -- never for the 194 MiB audio one.
            if self.size_hint and total and 0.5 <= self.size_hint / total <= 2:
                total = self.size_hint
        if not total:
            return
        now = time.time()
        with self.lock:
            if d.get("filename") != self.name:
                self.name = d.get("filename")    # a new stream; start over
                self.samples.clear()
                self.step = -1
            if self.samples:
                self.gaps.append(now - self.last_data)
            self.frags = frags
            self.total = total
            self.got = got
            # Fragment counts never go backwards, so they beat a ratio of two
            # moving numbers -- but the index only advances when the FIRST
            # outstanding fragment lands, so with eight in flight it can read
            # zero while 150 MiB is already on disk. Whichever says more.
            self.frac = max(done / frags if frags else 0.0,
                            got / total if total else 0.0)
            self.last_data = now
            self.active = True
            self.samples.append((now, self.got))
            while len(self.samples) > 2 and now - self.samples[0][0] > self.WINDOW:
                self.samples.popleft()
            if self.live:
                self._draw(now)
            elif (pct := int(100 * self.frac)) >= self.step + 10:
                self.step = pct                  # every 10%, not every chunk
                speed, eta = self._rate()
                self.log(f"    {pct:3d}%  {speed:.1f} MiB/s  left {eta}")

    def pp_hook(self, d):
        """Say when ffmpeg starts muxing, rather than guessing from a stream.

        The progress hook fires once per stream, so announcing the merge from
        there claimed it had begun the moment the video was done -- with the
        audio download, thirteen more minutes of it, still to come.
        """
        if d.get("status") == "started" and d.get("postprocessor") == "Merger":
            self.log("  Merging video and audio...")

    def close(self):
        with self.lock:
            self.closed = True
            self.active = False
            self._clear()

    # ------------------------------------------------------- drawing ----
    def _tick(self):
        while True:
            time.sleep(1.0)
            with self.lock:
                if self.closed:
                    return
                if self.active:
                    self._draw(time.time())

    def _stall_after(self):
        """How long silence has to last before it means something.

        A plain transfer reports every few kilobytes, so four seconds of
        nothing is already wrong. A fragmented one only reports when a
        fragment finishes, and those land in clumps: the workers finish
        their 10 MiB within a moment of each other, then nothing for ten
        seconds, then the next clump. So the gaps run [0.1, 0.1, 0.1, 10,
        0.1, ...] -- and the MEDIAN of that is 0.1, which pinned this to its
        floor and cried stall through every normal pause between clumps, for
        most of the download. The longest recent gap is the honest measure
        of the cycle. The cap stops one real hang, once it ages into the
        window, from blinding this to the next one.
        """
        if len(self.gaps) >= 2:
            return max(self.STALL_AFTER, min(1.5 * max(self.gaps), 90.0))
        return self.FRAG_STALL_AFTER if self.frags else self.STALL_AFTER

    def _rate(self):
        """(MiB/s over the trailing window, ETA text). No speed -> "?"."""
        speed = 0.0
        if len(self.samples) >= 2:
            first, last = self.samples[0], self.samples[-1]
            # A stall leaves no sample inside it, so the span has to be
            # measured to now, not to the last sample. Otherwise the average
            # keeps quoting the burst that has already finished.
            span = max(last[0] - first[0], time.time() - first[0])
            if span > 0:
                speed = (last[1] - first[1]) / span
        left = max(0, self.total - self.got)
        # eta in seconds as h:mm:ss. Printing mm:ss turns a two-hour wait
        # into "118:00", which reads like 118 hours.
        return speed / 2**20, _hms(left / speed) if speed > 512 else "?"

    def _draw(self, now):
        pct = min(100, int(100 * self.frac))
        bar = "#" * (pct // 4) + "-" * (25 - pct // 4)
        speed, eta = self._rate()
        idle = now - self.last_data
        if idle >= self._stall_after():
            tail = f"{'stalled ' + str(int(idle)) + 's':>12}  left {eta}"
        else:
            tail = f"{speed:5.1f} MiB/s  left {eta}"
        line = (f"  [{bar}] {pct:3d}%  {self.got/2**30:5.2f}/"
                f"{self.total/2**30:.2f} GiB  {tail}")
        print("\r" + line.ljust(78), end="", flush=True)

    def _clear(self):
        if self.live:
            print("\r" + " " * 78 + "\r", end="", flush=True)
