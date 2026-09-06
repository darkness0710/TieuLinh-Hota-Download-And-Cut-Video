"""A local web page that runs the pipeline and shows where each job is.

    python -m tlh.web            then open http://127.0.0.1:8765
    web.cmd                      the same, and opens the browser

Why this exists: the console tells you what is happening only while its window
is open. Close it and there is no way left to ask "has that link finished
downloading", which is the first thing anyone who is not the author wants to
know. So every job gets a record under work/jobs/ that outlives the window.

Three deliberate choices:

* **Standard library only.** No FastAPI, no uvicorn, nothing to pip install.
  A web page is not worth another dependency that can fail to install on a
  machine where the point was to avoid installing things.

* **Nothing in the pipeline changed.** This spawns `run.py` as a subprocess
  and reads its output, rather than reaching inside it. The pipeline works;
  a new interface should not be able to break it. The cost is that this parses
  our own console output -- see PATTERNS -- so a change to a progress line
  shows up here as a stage without a percentage rather than as a crash. Jobs
  started from Start.cmd are also invisible to this page.

* **127.0.0.1 only.** This endpoint starts processes. It must not be reachable
  from the network, so it never binds 0.0.0.0.
"""
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import fetch, ffmpeg, jsruntime, naming
from .config import ROOT
from .webpage import PAGE

JOBS_DIR = ROOT / "work" / "jobs"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
VIDEO_EXT = (".mp4", ".mkv", ".ts", ".flv", ".mov", ".webm", ".avi")
# What a browser will be told a preview is. Only the first two are formats a
# browser actually plays; the rest are served honestly and will simply refuse
# to play, which is a clearer outcome than mislabelling them.
MEDIA_TYPE = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/mp4",
              ".mkv": "video/x-matroska", ".ts": "video/mp2t",
              ".flv": "video/x-flv", ".avi": "video/x-msvideo"}
MEDIA_CHUNK = 1 << 20           # bytes per write while streaming a preview
TRIM_MIN = 2.0                  # seconds; shorter than this is a mis-click
# Two addresses for the same person: the main channel, and the backup he
# streams from when the main one is down. Kept as a list because the picker
# offers both, and CHANNEL stays the default for every caller that asks for
# none.
CHANNELS = (
    {"url": "https://www.youtube.com/@TieulinhHOTA", "name": "@TieulinhHOTA"},
    {"url": "https://www.youtube.com/@Tieulinh2",
     "name": "@Tieulinh2 (backup)"},
)
CHANNEL = CHANNELS[0]["url"]
CHANNEL_TTL = 120.0            # seconds a channel listing is reused for
LOG_TAIL = 400                  # lines kept per job for the details view
ACTIVE_STAGES = ("queued", "downloading", "analysing", "rendering")

# --------------------------------------------------------------- lifetime ----
# Measured: killing this process without letting it clean up leaves both the
# run.py child and its ffmpeg grandchild running, burning CPU and bandwidth
# with no interface left to stop them. Ctrl+C is handled below, but a click on
# the window's X, or End Task, never reaches that handler.
#
# A job object with KILL_ON_JOB_CLOSE is what survives all of those: the
# kernel kills every process in the job when the last handle to it closes,
# which happens when this process dies, however it dies. Descendants inherit
# the job, so ffmpeg and aria2c are covered too.
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BASIC_LIMITS(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_ulong),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_ulong),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_ulong),
                ("SchedulingClass", ctypes.c_ulong)]


class _EXTENDED_LIMITS(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BASIC_LIMITS),
                ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _kill_on_close_job():
    """A job object whose processes die with this one. None if unavailable."""
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.CreateJobObjectW(None, None)
        if not handle:
            return None
        info = _EXTENDED_LIMITS()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(
                handle, JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            return None
        return handle
    except (OSError, AttributeError):
        return None


def _adopt(proc):
    """Put a child in the job, so it cannot outlive this process."""
    global _job
    with _job_lock:
        if _job is None:
            _job = _kill_on_close_job() or False
        handle = _job
    if not handle:
        return False
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return bool(k32.AssignProcessToJobObject(handle, int(proc._handle)))
    except (OSError, AttributeError, ValueError):
        return False


_job = None
_job_lock = threading.Lock()

_lock = threading.Lock()
_jobs = {}                      # id -> record
_procs = {}                     # id -> Popen, for cancelling


# ----------------------------------------------------------------- state ----
def _save(job):
    """Write one job's record, atomically: the page may read at any moment."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{job['id']}.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _load_jobs():
    """Records from previous runs of this server, so history survives it."""
    if not JOBS_DIR.is_dir():
        return
    for path in sorted(JOBS_DIR.glob("*.json")):
        try:
            job = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # Nothing is running any more: this process just started. A job left
        # mid-flight was killed with the window that owned it, and saying so
        # is better than showing a progress bar frozen at 41% for ever.
        if job.get("stage") in ACTIVE_STAGES:
            job["stage"] = "interrupted"
            job["detail"] = "the run that owned this job is gone"
            _save(job)
        _jobs[job["id"]] = job


def _update(job_id, **fields):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        now = time.time()
        # How often this job actually says anything. A download bar reports
        # several times a second; the render reports once per finished piece,
        # twenty or thirty seconds apart. One fixed threshold cannot tell a
        # quiet stage from a stuck one, so the page gets this number and
        # scales its own warning by it.
        gap = now - job.get("updated", now)
        if gap > 0.2:
            recent = job.setdefault("gaps", [])
            recent.append(round(gap, 1))
            del recent[:-5]
            job["gap"] = max(recent)
        job.update(fields)
        job["updated"] = now
        _save(job)


# ---------------------------------------------------------------- parsing ----
# Each entry is (compiled pattern, handler). The handler gets the match and
# returns the fields to merge into the job record. Ordered by how often a line
# turns up, because every line is tried against every pattern.
def _num(text):
    return float(text.replace(",", "")) if text else 0.0


PATTERNS = [
    # aria2c's own readout, which is the only progress a download through it
    # produces: yt-dlp hands the transfer over and hears nothing until it ends.
    (re.compile(r"\[#\w+\s+([\d.]+)(\w+)/([\d.]+)(\w+)\((\d+)%\)\s+CN:(\d+)\s+DL:\s*([\d.]+)(\w+)(?:\s+ETA:(\S+))?"),
     lambda m: {"stage": "downloading", "percent": int(m.group(5)),
                "detail": f"{m.group(1)}{m.group(2)} of {m.group(3)}{m.group(4)}"
                          f"   {m.group(7)}{m.group(8)}/s   {m.group(6)} connections"
                          + (f"   còn {m.group(9)}" if m.group(9) else "")}),
    # our own one-line download bar, used when aria2c is not installed
    (re.compile(r"^\s*\[[#-]+\]\s+(\d+)%\s+([\d.]+)/([\d.]+) GiB\s+(.*?)\s*$"),
     lambda m: {"stage": "downloading", "percent": int(m.group(1)),
                "detail": f"{m.group(2)}/{m.group(3)} GiB   {m.group(4).strip()}"}),
    (re.compile(r"^\[download\]\s+100% of\s+([\d.]+\w+) in (\S+) at (\S+)"),
     lambda m: {"detail": f"stream done: {m.group(1)} in {m.group(2)} at {m.group(3)}"}),
    (re.compile(r"^\s*signal\s+(\d+)%\s+(\S+) elapsed(?:\s+eta (\S+))?"),
     lambda m: {"stage": "analysing", "percent": int(m.group(1)),
                "detail": "pass 1/4, clock + seat signal"
                          + (f"   còn {m.group(3)}" if m.group(3) else "")}),
    (re.compile(r"^\s*screens\s+(\d+)%\s+(\S+) of (\S+)"),
     lambda m: {"stage": "analysing", "percent": int(m.group(1)),
                "detail": f"pass 2/4, lobby / menu screens   {m.group(2)} of {m.group(3)}"}),
    (re.compile(r"^\s*map vs combat\s+(\d+)%\s+(\S+) of (\S+)"),
     lambda m: {"stage": "analysing", "percent": int(m.group(1)),
                "detail": f"pass 3/4, map vs combat   {m.group(2)} of {m.group(3)}"}),
    (re.compile(r"^\s*(\d+)/(\d+)\s+([\d.]+)min elapsed\s+eta ([\d.]+)min"),
     lambda m: {"stage": "rendering",
                "percent": int(100 * int(m.group(1)) / max(1, int(m.group(2)))),
                "detail": f"piece {m.group(1)} of {m.group(2)}   còn ~{m.group(4)} phút"}),
    (re.compile(r"^\s*Title\s+(.+?)\s*$"), lambda m: {"title": m.group(1)}),
    (re.compile(r"^\s*Size\s+(.+?)\s*$"), lambda m: {"size": m.group(1)}),
    (re.compile(r"^\s*Streams\s+(.+?)\s*$"), lambda m: {"streams": m.group(1)}),
    (re.compile(r"^\s*Downloader\s+(.+?)\s*$"), lambda m: {"downloader": m.group(1)}),
    (re.compile(r"^\s*Resuming\s+(.+?)\s*$"), lambda m: {"detail": "resuming: " + m.group(1)}),
    (re.compile(r"^\s*Downloaded\s+(.+?)\s*$"),
     lambda m: {"stage": "analysing", "percent": 0, "file": m.group(1),
                "detail": "download finished"}),
    (re.compile(r"^\s*\[[\d:]+\]\s+\[1/4\]"),
     lambda m: {"stage": "analysing", "percent": 0, "detail": "pass 1/4 starting"}),
    (re.compile(r"^\s*\[[\d:]+\]\s+\[4/4\] render"),
     lambda m: {"stage": "rendering", "percent": 0, "detail": "render starting"}),
    (re.compile(r"^\s*segments (\d+)\s+kept (\S+) \(([\d.]+)%\)"),
     lambda m: {"segments": int(m.group(1)),
                "kept": f"{m.group(2)} ({m.group(3)}%)"}),
    # "19 chapters -> D:\...\Stream.txt" carries the path as well as the
    # count, and the path is the thing anyone actually wants: it is the file
    # whose contents go in the YouTube description.
    (re.compile(r"^\s*(\d+) chapters -> (.+?)\s*$"),
     lambda m: {"chapters": int(m.group(1)), "chapters_path": m.group(2)}),
    (re.compile(r"^\s*chapters\s+(.+\.txt)\s*$"),
     lambda m: {"chapters_path": m.group(1)}),
    (re.compile(r"^\s*file\s+(.+?)\s*$"), lambda m: {"file": m.group(1)}),
    (re.compile(r"^\s*length\s+(\S+)\s*$"), lambda m: {"length": m.group(1)}),
    (re.compile(r"^\s*done\s+(.+?)\s{3,}([\d.]+ GiB)"),
     lambda m: {"output": m.group(1), "output_size": m.group(2)}),
    # --download-only ends here instead. Same two fields, because the card
    # already knows how to show a path and a size; it reads the mode to decide
    # what to call them.
    (re.compile(r"^\s*saved\s+(.+?)\s{3,}([\d.]+ GiB)"),
     lambda m: {"output": m.group(1), "output_size": m.group(2),
                "detail": "đã tải xong, không cắt"}),
    (re.compile(r"^\s*(\d+) video\(s\) in ([\d.]+) min total"),
     lambda m: {"detail": f"{m.group(1)} video theo game, {m.group(2)} phút"}),
    (re.compile(r"^\s*game (\d+)\s+(\S+) in (\d+) segment"),
     lambda m: {"stage": "rendering",
                "detail": f"game {m.group(1)}: {m.group(2)} trong {m.group(3)} đoạn"}),
    (re.compile(r"^\s*already rendered as (.+?), skipping"),
     lambda m: {"stage": "done", "percent": 100,
                "detail": "already rendered: " + m.group(1)}),
    # Anything that means the run is not going to finish quietly.
    (re.compile(r"^\s*WARNING\s+no JavaScript runtime"),
     lambda m: {"warning": "no deno: downloads run about 50x slower"}),
    (re.compile(r"^\s*could not read this link: (.+?)\s*$"),
     lambda m: {"error": m.group(1)}),
    (re.compile(r"^\s*download failed: (.+?)\s*$"), lambda m: {"error": m.group(1)}),
    (re.compile(r"^ERROR:\s+(.+?)\s*$"), lambda m: {"error": m.group(1)}),
    (re.compile(r"^\s*NOT ENOUGH SPACE\.\s+(.+?)\s*$"), lambda m: {"error": m.group(1)}),
]


def _parse(line):
    for pattern, handler in PATTERNS:
        m = pattern.search(line)
        if m:
            return handler(m)
    return None


# ----------------------------------------------------------------- runner ----
def _reader(job_id, proc, log_path):
    """Follow the child's output and turn it into job state.

    Read in chunks and split on BOTH newline and carriage return: the download
    bar and aria2c's readout redraw one line with \\r and never send a newline,
    so a line iterator would show nothing at all for the length of a download.
    """
    buf, log = "", open(log_path, "a", encoding="utf-8")
    try:
        while True:
            chunk = proc.stdout.read1(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            parts = re.split(r"[\r\n]", buf)
            buf = parts.pop()               # keep the unfinished tail
            for line in parts:
                if not line.strip():
                    continue
                log.write(line + "\n")
                log.flush()
                with _lock:
                    job = _jobs.get(job_id)
                    if job is not None:
                        job.setdefault("log", []).append(line)
                        del job["log"][:-LOG_TAIL]
                fields = _parse(line)
                if fields:
                    _update(job_id, **fields)
    finally:
        log.close()
    code = proc.wait()
    with _lock:
        job = _jobs.get(job_id, {})
        cancelled = job.get("stage") == "cancelled"
    if cancelled:
        pass
    elif code == 0:
        _update(job_id, stage="done", percent=100, finished=time.time(),
                detail="finished")
    else:
        _update(job_id, stage="failed", finished=time.time(),
                detail=f"run.py exited {code}")
    with _lock:
        _procs.pop(job_id, None)


def start_job(url=None, filename=None, mode="full"):
    """Spawn run.py for one URL or one file in input/. Returns the job id."""
    args = [sys.executable, "run.py", "--live-progress"]
    if url:
        args += ["--url", url]
    else:
        args += ["--file", filename]
    if mode == "segments":
        args.append("--dry-run")
    elif mode == "parts":
        args.append("--parts-only")
    elif mode == "games":
        args.append("--per-game")
    elif mode == "download":
        args.append("--download-only")

    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "url": url, "file": filename, "mode": mode,
           "stage": "queued", "percent": 0, "detail": "starting",
           "title": url or filename, "started": time.time(),
           "updated": time.time(), "log": []}
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_DIR / f"{job_id}.log"
    with _lock:
        _jobs[job_id] = job
    _save(job)

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        args, cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    adopted = _adopt(proc)
    with _lock:
        _procs[job_id] = proc
    _update(job_id, stage="downloading" if url else "analysing", pid=proc.pid,
            adopted=adopted)
    threading.Thread(target=_reader, args=(job_id, proc, log_path),
                     daemon=True).start()
    return job_id


def delete_job(job_id):
    """Forget one finished job: its record and its log, nothing else.

    Deliberately refuses while it is still working. Removing the record of a
    running job would leave the process going with nothing left to stop it
    from, and the reader thread would write the file straight back.
    """
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False, "không có việc này"
        if job.get("stage") in ACTIVE_STAGES:
            return False, "việc này đang chạy -- bấm Dừng trước rồi xoá"
        _jobs.pop(job_id, None)
    for suffix in (".json", ".log"):
        try:
            os.remove(JOBS_DIR / f"{job_id}{suffix}")
        except OSError:
            pass
    return True, "đã xoá khỏi danh sách"


def cancel_job(job_id):
    with _lock:
        proc = _procs.get(job_id)
    if not proc:
        return False
    # taskkill /T, not proc.terminate(): the work is being done by ffmpeg and
    # aria2c children, and killing only the python parent leaves them running.
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                   capture_output=True)
    _update(job_id, stage="cancelled", detail="stopped from the web page",
            finished=time.time())
    return True


# ------------------------------------------------------------------- http ----
def _reveal(where, name=None):
    """Open one of our own folders in Explorer. Returns (ok, message).

    A browser cannot do this: a file:// link from an http:// page is blocked,
    and would show a listing in a tab rather than Explorer. The server can,
    because it is running in the same desktop session as the person clicking.

    `where` names a folder from the table below -- it is never a path from the
    request. Taking a path would turn this into "open anything on this
    machine", and with /select it would report whether a given file exists.

    explorer.exe exits 1 even when it worked, so os.startfile is used for a
    folder and the return code is ignored for a file.
    """
    folders = {"input": INPUT_DIR, "output": OUTPUT_DIR,
               "work": ROOT / "work", "root": ROOT}
    target = folders.get(where)
    if target is None:
        return False, "không mở chỗ đó"
    if not target.is_dir():
        return False, f"chưa có thư mục {target}"
    if name:
        # One file inside it, selected. A bare name only, so nothing can walk
        # out of the folder.
        if name != os.path.basename(name):
            return False, "tên file không hợp lệ"
        picked = target / name
        if not picked.exists():
            return False, "không còn file đó"
        # The command line has to be built by hand. explorer parses its own,
        # and a list argument would have Python quote the whole "/select,PATH"
        # as one token -- explorer then reads it as a single path and OPENS
        # the file in whatever plays mp4 on this machine, which is the
        # opposite of the intent. The quotes belong around the path only.
        # A Windows filename cannot contain a double quote, so this is safe.
        done = subprocess.run(f'explorer /select,"{picked}"', capture_output=True)
        # explorer exits 1 even when it worked, so its code says nothing. Fall
        # back to the plain folder only if it could not be started at all.
        if done.returncode not in (0, 1):
            os.startfile(str(target))
            return True, f"đã mở {target}"
        return True, f"đã mở Explorer, chọn {picked.name}"
    try:
        os.startfile(str(target))
    except OSError as exc:
        return False, str(exc)
    return True, f"đã mở {target}"


def _recycle_many(paths):
    """Send several files to the Recycle Bin in one PowerShell call.

    One call, not one per file: starting PowerShell costs about a second, and
    a folder being cleared can hold a dozen leftovers. The list travels in an
    environment variable, newline separated -- a Windows path cannot contain a
    newline, and quoting a dozen Vietnamese filenames into a command line is
    how an injection bug gets written.
    """
    paths = [str(p) for p in paths]
    if not paths:
        return 0, ""
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "$env:TLH_DELETE -split [char]10 | Where-Object { $_ } | ForEach-Object { "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_, "
        "[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, "
        "[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin) }")
    done = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=dict(os.environ, TLH_DELETE="\n".join(paths)),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    gone = sum(1 for p in paths if not os.path.exists(p))
    return gone, (done.stderr or "").strip()[:200]


def _any_active():
    """Id of a job that is still working, if there is one."""
    with _lock:
        for job in _jobs.values():
            if job.get("stage") in ACTIVE_STAGES:
                return job["id"]
    return None


def clear_folder(where):
    """Everything in input/ or output/ to the Recycle Bin. Returns (ok, text).

    Only those two. work/ is deliberately not on the list: clearing it would
    take signal.npz caches and index.json with it, and Clear.cmd already does
    that carefully, sparing the index so a re-run does not render a duplicate
    under a "(2)" name.
    """
    folders = {"input": INPUT_DIR, "output": OUTPUT_DIR}
    target = folders.get(where)
    if target is None:
        return False, "chỉ dọn được input hoặc output"
    if not target.is_dir():
        return False, "chưa có thư mục đó"
    busy = _any_active()
    if busy:
        return False, "đang có việc chạy -- dừng nó trước khi dọn"
    files = sorted(p for p in target.iterdir() if p.is_file())
    if not files:
        return True, "không có gì để dọn"
    size = sum(p.stat().st_size for p in files)
    gone, err = _recycle_many(files)
    text = f"đã chuyển {gone}/{len(files)} file ({size / 2**30:.2f} GiB) vào Thùng rác"
    if gone < len(files):
        return False, text + (f" -- {err}" if err else "")
    return True, text


def _recycle(path):
    """Send one file to the Recycle Bin. Returns (ok, message).

    Not os.remove: a mistake here costs a six gigabyte download and half an
    hour of getting it back. scripts/clear.ps1 deletes the same way, so
    whichever route removed a file, it is recoverable from the same place.

    The path travels in an environment variable rather than inside the script
    text -- these filenames carry brackets, apostrophes and spaces, and
    quoting them into a command line is how an injection bug gets written.
    """
    script = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
              "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
              "$env:TLH_DELETE, "
              "[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, "
              "[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)")
    del script          # one implementation, in _recycle_many
    gone, err = _recycle_many([path])
    if gone:
        return True, "moved to the Recycle Bin"
    return False, err or "failed"


def _busy_with(name):
    """An id of a running job working on this file, if there is one."""
    with _lock:
        for job in _jobs.values():
            if job.get("stage") not in ACTIVE_STAGES:
                continue
            used = job.get("file") or ""
            if used == name or os.path.basename(used) == name:
                return job["id"]
    return None


def input_video(name):
    """Path of `name` in input/, or None if it is not a video sitting there.

    One rule for every endpoint that takes a filename from the page: a bare
    basename, no separators, that exists in input/ and looks like a video.
    Nothing here is ever passed through a shell.
    """
    if not name or name != os.path.basename(name):
        return None
    path = INPUT_DIR / name
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXT:
        return None
    return path


def _listing(folder):
    if not folder.is_dir():
        return []
    out = []
    for entry in sorted(folder.iterdir()):
        # A leftover half of an interrupted download ends in .mp4 too.
        # Offering it with a Run button invites an hour of work on a file
        # with no sound in it.
        if (entry.is_file() and entry.suffix.lower() in VIDEO_EXT
                and not fetch.is_partial(entry.name)):
            out.append({"name": entry.name, "bytes": entry.stat().st_size})
    return out


def trim_clip(name, start, end):
    """Copy [start, end) of an input video out to a new file in input/.

    Stream copy, not a re-encode: a ninety-minute cut out of a four-hour VOD
    takes seconds this way and minutes the other, and the pixels are the
    original ones. The price is that -ss lands on the keyframe at or before
    `start`, so a clip can begin a second or two early -- which for cutting a
    test piece down to something quick to run does not matter, and the page
    says so rather than implying frame accuracy.
    """
    src = input_video(name)
    if src is None:
        return None, "không có file đó trong input/"
    try:
        start, end = float(start), float(end)
    except (TypeError, ValueError):
        return None, "mốc thời gian không đọc được"
    length = ffmpeg.duration(str(src)) or 0.0
    if not 0 <= start < end or (length and start >= length):
        return None, "điểm đầu phải nhỏ hơn điểm cuối và nằm trong video"
    if length:
        end = min(end, length)
    if end - start < TRIM_MIN:
        return None, f"đoạn quá ngắn (dưới {TRIM_MIN:.0f} giây)"

    out_name = naming.clip_name(src.name, start, end, folder=str(INPUT_DIR))
    out = INPUT_DIR / out_name
    cmd = [ffmpeg.FF, "-ss", f"{start:.3f}", "-i", str(src),
           "-t", f"{end - start:.3f}", "-c", "copy",
           "-avoid_negative_ts", "make_zero", "-y", str(out)]
    done = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode or not out.is_file():
        if out.is_file():
            out.unlink(missing_ok=True)
        tail = (done.stderr or "").strip().splitlines()[-1:] or ["ffmpeg lỗi"]
        return None, tail[0][:200]
    return {"name": out_name, "bytes": out.stat().st_size,
            "length": ffmpeg.duration(str(out)) or (end - start)}, "đã cắt"


_channel_cache = {}             # (url, limit) -> (fetched_at, entries)


def channel_streams(url=None, limit=10):
    """One channel's livestreams, newest first, as the tab already orders them.

    A FLAT listing: yt-dlp is told not to open each video's player API, so
    this needs no JavaScript runtime, cannot be throttled the way a download
    is, and returns everything a picker needs -- id, title, duration, views,
    timestamp, thumbnail and live_status. Measured on a real channel: fifty
    entries in 1.1 seconds, one request.

    Cached for a moment because the obvious thing to do with a 10/20/100
    dropdown is to try all three, and repeated listings from one address are
    what earns a 429.
    """
    try:
        import yt_dlp
    except ImportError:
        return None, "yt-dlp chưa được cài"

    target = (url or CHANNEL).rstrip("/")
    if urlparse(target).scheme not in ("http", "https") \
            or "youtube.com" not in urlparse(target).netloc:
        return None, "chỉ nhận link youtube.com"
    if not target.endswith("/streams"):
        target += "/streams"
    limit = max(1, min(int(limit or 10), 100))

    key = (target, limit)
    hit = _channel_cache.get(key)
    if hit and time.time() - hit[0] < CHANNEL_TTL:
        return hit[1], "cache"

    opts = {"quiet": True, "no_warnings": True,
            "extract_flat": "in_playlist", "playlistend": limit}
    deno = jsruntime.find()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        return None, str(exc).strip().splitlines()[0][:200]

    out = []
    for entry in (info.get("entries") or []):
        if not entry:
            continue
        thumbs = entry.get("thumbnails") or []
        out.append({
            "id": entry.get("id"),
            "title": entry.get("title") or "",
            "url": entry.get("url") or
                   f"https://www.youtube.com/watch?v={entry.get('id')}",
            "duration": entry.get("duration"),
            "views": entry.get("view_count"),
            "when": entry.get("timestamp"),
            "live": entry.get("live_status"),
            # The listing usually carries one; the id-based address always
            # exists, so it is the fallback rather than the first choice.
            "thumb": (thumbs[-1].get("url") if thumbs else
                      f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"),
        })
    _channel_cache[key] = (time.time(), out)
    return out, f"{len(out)} video"


_date_cache = {}                # video id -> epoch seconds, or None


def video_date(video_id):
    """When one video was streamed. One request, then remembered.

    The flat channel listing does not carry a date -- measured on a real
    channel, every entry came back with timestamp None -- and the only place
    it exists is the video's own metadata. That is a player request each, so
    it happens per video, when asked for, rather than for a hundred rows
    nobody looked at.

    release_timestamp, not upload_date: naming.py picks the same field for
    the same reason, that a stream starting after local midnight is still the
    previous day in UTC.
    """
    if not video_id or not re.fullmatch(r"[\w-]{5,20}", video_id):
        return None, "id không hợp lệ"
    if video_id in _date_cache:
        return _date_cache[video_id], "cache"
    try:
        import yt_dlp
    except ImportError:
        return None, "yt-dlp chưa được cài"
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    deno = jsruntime.find()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception as exc:
        return None, str(exc).strip().splitlines()[0][:160]
    when = info.get("release_timestamp") or info.get("timestamp")
    _date_cache[video_id] = when
    return when, "ok"


def _folder_stats(folder):
    """(bytes, file count) for one folder, everything in it.

    Not just the videos: input/ also holds the leftovers of an interrupted
    download, and those are what fill a disk. Walked rather than listed,
    because output/ carries the chapter files beside each video.
    """
    total = count = 0
    if not folder.is_dir():
        return {"bytes": 0, "files": 0}
    for root, _dirs, names in os.walk(folder):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
                count += 1
            except OSError:
                pass
    return {"bytes": total, "files": count}


def _state():
    usage = shutil.disk_usage(str(ROOT))
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j.get("started", 0),
                      reverse=True)
        jobs = [{k: v for k, v in j.items() if k not in ("log", "gaps")}
                for j in jobs]
    return {"now": time.time(),
            "drive": {"root": str(ROOT.drive or ROOT), "used": usage.used,
                      "free": usage.free, "total": usage.total},
            # Absolute, not "input\": the person reading this page has to be
            # able to find the folder in Explorer without knowing where the
            # project lives.
            "paths": {"root": str(ROOT), "input": str(INPUT_DIR),
                      "output": str(OUTPUT_DIR),
                      "parts": os.path.join(str(ROOT), "work",
                                            "<tên video>", "parts") + os.sep},
            "folders": {"input": _folder_stats(INPUT_DIR),
                        "output": _folder_stats(OUTPUT_DIR)},
            "inputs": _listing(INPUT_DIR), "outputs": _listing(OUTPUT_DIR),
            "jobs": jobs}


class Handler(BaseHTTPRequestHandler):
    server_version = "tieu_linh_hota"

    def log_message(self, *args):
        pass                                # a request log per second is noise

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _media(self):
        """The input video this request names, or None once 404 is sent."""
        name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
        target = input_video(name)
        if target is None:
            self._send(404, json.dumps({"error": "no such file in input/"}))
            return None
        return target

    def _send_media(self, path, head=False):
        """Serve a file in byte ranges, so a browser can seek inside it.

        This is the only endpoint that sends file CONTENT rather than facts
        about it, and ranges are what make it worth having: without
        Accept-Ranges a <video> must read from byte zero to reach two hours
        in, which on a 7 GiB VOD means it never gets there. With them, a seek
        is one request for one megabyte.
        """
        size = path.stat().st_size
        ctype = MEDIA_TYPE.get(path.suffix.lower(), "application/octet-stream")
        asked = (self.headers.get("Range") or "").strip()
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", asked)
        start, end, partial = 0, size - 1, False

        if asked and not match:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        if match:
            lo, hi = match.group(1), match.group(2)
            if lo:
                start = int(lo)
                if hi:
                    end = min(int(hi), size - 1)
            elif hi:                        # "bytes=-N" means the last N
                start = max(0, size - int(hi))
            else:
                start, end = 0, size - 1    # "bytes=-" names nothing
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if head:
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(MEDIA_CHUNK, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except ConnectionError:
                    # A <video> drops the range it is reading the moment the
                    # viewer seeks somewhere else. Normal, not an error -- and
                    # ConnectionError rather than the two named subclasses,
                    # because Windows raises ConnectionAbortedError for a
                    # local abort and the narrower catch printed a traceback
                    # for every seek.
                    return
                left -= len(chunk)

    def do_HEAD(self):
        if urlparse(self.path).path == "/media":
            target = self._media()
            if target is not None:
                self._send_media(target, head=True)
            return
        self.send_response(501)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/state":
            return self._send(200, json.dumps(_state(), ensure_ascii=False))
        if path == "/media":
            target = self._media()
            return self._send_media(target) if target is not None else None
        m = re.fullmatch(r"/api/jobs/(\w+)/log", path)
        if m:
            with _lock:
                job = _jobs.get(m.group(1))
                lines = list(job.get("log", [])) if job else None
            if lines is None:
                return self._send(404, json.dumps({"error": "no such job"}))
            return self._send(200, json.dumps({"log": lines}, ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, json.dumps({"error": "bad json"}))

        if path == "/api/jobs":
            mode = body.get("mode", "full")
            if mode not in ("full", "parts", "segments", "games", "download"):
                return self._send(400, json.dumps({"error": "bad mode"}))
            # Downloading is something you do TO a link. A file in input/ has
            # already been downloaded, so the pair is not a choice anyone
            # meant to make.
            if mode == "download" and not body.get("url"):
                return self._send(400, json.dumps(
                    {"error": "chế độ chỉ tải về cần một link YouTube, "
                              "không dùng được với file đã có trong input/"},
                    ensure_ascii=False))
            url, name = (body.get("url") or "").strip(), body.get("file")
            if url:
                # Only http(s), and never through a shell: this argument comes
                # from a text box.
                if urlparse(url).scheme not in ("http", "https"):
                    return self._send(400, json.dumps({"error": "not an http link"}))
                return self._send(200, json.dumps({"id": start_job(url=url, mode=mode)}))
            if name:
                # A basename that exists in input/, so nothing can point this
                # at another folder.
                if input_video(name) is None:
                    return self._send(400, json.dumps({"error": "no such file in input/"}))
                return self._send(200, json.dumps({"id": start_job(filename=name, mode=mode)}))
            return self._send(400, json.dumps({"error": "give a url or a file"}))

        if path == "/api/trim":
            clip, message = trim_clip(body.get("name"), body.get("start"),
                                      body.get("end"))
            if clip is None:
                return self._send(400, json.dumps({"error": message},
                                                  ensure_ascii=False))
            return self._send(200, json.dumps(dict(clip, message=message),
                                              ensure_ascii=False))

        if path == "/api/channels":
            return self._send(200, json.dumps({"channels": list(CHANNELS)},
                                              ensure_ascii=False))

        if path == "/api/channel":
            entries, message = channel_streams(body.get("url"),
                                               body.get("limit", 10))
            if entries is None:
                return self._send(502, json.dumps({"error": message},
                                                  ensure_ascii=False))
            return self._send(200, json.dumps(
                {"channel": (body.get("url") or CHANNEL), "note": message,
                 "entries": entries}, ensure_ascii=False))

        if path == "/api/video-date":
            when, message = video_date(body.get("id"))
            return self._send(200 if when else 502,
                              json.dumps({"when": when, "note": message},
                                         ensure_ascii=False))

        if path == "/api/folders/clear":
            ok, message = clear_folder(body.get("where"))
            return self._send(200 if ok else 409,
                              json.dumps({"cleared": ok, "message": message}
                                         if ok else
                                         {"cleared": ok, "error": message},
                                         ensure_ascii=False))

        if path == "/api/reveal":
            ok, message = _reveal(body.get("where"), body.get("file"))
            return self._send(200 if ok else 400,
                              json.dumps({"opened": ok, "message": message},
                                         ensure_ascii=False))

        if path == "/api/files/delete":
            name = body.get("file") or ""
            target = INPUT_DIR / name
            if name != os.path.basename(name) or not target.is_file():
                return self._send(400, json.dumps({"error": "no such file in input/"}))
            busy = _busy_with(name)
            if busy:
                return self._send(409, json.dumps(
                    {"error": "một việc đang chạy dùng file này -- dừng nó trước"}))
            ok, message = _recycle(target)
            return self._send(200 if ok else 500,
                              json.dumps({"deleted": ok, "message": message},
                                         ensure_ascii=False))

        m = re.fullmatch(r"/api/jobs/(\w+)/delete", path)
        if m:
            ok, message = delete_job(m.group(1))
            return self._send(200 if ok else 409,
                              json.dumps({"deleted": ok, "error": message}
                                         if not ok else
                                         {"deleted": ok, "message": message},
                                         ensure_ascii=False))

        m = re.fullmatch(r"/api/jobs/(\w+)/cancel", path)
        if m:
            ok = cancel_job(m.group(1))
            return self._send(200 if ok else 409,
                              json.dumps({"cancelled": ok}))
        self._send(404, json.dumps({"error": "not found"}))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open a browser too")
    args = ap.parse_args(argv)

    _load_jobs()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  tieu_linh_hota   {url}")
    print("  Ctrl+C to stop. Jobs keep running only while this window is open.\n")
    if args.open:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopping")
        with _lock:
            running = list(_procs.items())
        for job_id, proc in running:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True)
            _update(job_id, stage="interrupted", detail="the server was stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
