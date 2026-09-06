"""Where aria2c lives, and why the download wants it.

googlevideo serves one connection at about 1 MiB/s. The cap is per
connection, so the way to go faster is to hold several at once -- but HOW
they are held matters. yt-dlp's own answer is a new connection per 10 MiB
fragment, some 600 of them for one VOD at roughly one a second, and this
line stops answering new ones after a quarter of an hour of that: SYNs into
the void, WinError 10060, workers idling in timeouts until four of them
together managed less than a single fresh connection.

aria2c opens its connections once and keeps them, each streaming a large
contiguous range: eight connections for the whole download instead of six
hundred. It also writes every range at its true offset in a file it sizes
up front, so a range that fails leaves a hole rather than shifting the rest
of the file -- the failure that yt-dlp's fragment skipping causes.

Measured on the [LKnJTE1fPyg] VOD at 21:07, on a line that was doing 11.5
MiB/s three hours earlier and was down to 0.67 with yt-dlp's fragments:
aria2c with 8 connections held 2.0 MiB/s. With 16 it opened all of them and
got nothing at all -- the same wall, reached from the other side.
"""
import os
import re
import subprocess
from pathlib import Path

from .config import ROOT

INSTALL_HINT = "winget install aria2.aria2   (or re-run Install.cmd)"

WHY = ("It holds 8 long-lived connections instead of opening 600 short ones, "
       "which is what this line refuses to keep doing.")


def _version(exe):
    """The version `exe --version` reports, or None."""
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=20).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"aria2 version (\S+)", out)
    return m.group(1) if m else None


def _candidates():
    yield ROOT / ".tools" / "aria2c.exe"
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet"
        yield winget / "Links" / "aria2c.exe"
        # The portable package unpacks into a version-stamped folder of its
        # own -- Packages/aria2.aria2_.../aria2-1.37.0-win-64bit-build1/ --
        # so this has to look deeper than one level.
        for found in sorted(winget.glob("Packages/aria2.aria2*/**/aria2c.exe")):
            yield found
    from shutil import which
    on_path = which("aria2c")
    if on_path:
        yield Path(on_path)


def find():
    """Path of an aria2c, as a string, or None."""
    seen = set()
    for path in _candidates():
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and _version(path):
            return str(path)
    return None


def describe():
    """(path, version) of the aria2c the download will use, or (None, None)."""
    path = find()
    return (path, _version(path)) if path else (None, None)
