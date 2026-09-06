"""Where the JavaScript runtime that YouTube downloads depend on lives.

yt-dlp has to run YouTube's own JavaScript to solve the `n` parameter of a
stream URL. Without a runtime it falls back to a player client whose URLs
carry no solved `n`, and googlevideo then answers with about 10 MiB per
request and stalls for the best part of a minute between them. Measured on
the [LKnJTE1fPyg] VOD: 165 KB/s against 11 MiB/s, so 6 GiB went from ten
minutes to ten hours. Nothing errors -- the download just runs fifty times
slower, and the progress bar, which only redraws when bytes arrive, sits
frozen showing the speed of the last burst.

Deno is the runtime to install. yt-dlp only enables deno by default, only
deno and bun have a solver script vendored inside yt-dlp, and node is
rejected below v22. setup.ps1 installs it; .tools/ is where it puts a copy
when winget is not available, and that copy is looked at first because PATH
is exactly what a per-user install cannot be relied on to have.
"""
import os
import re
import subprocess
from pathlib import Path

from .config import ROOT

# yt_dlp/utils/_jsruntime.py DenoJsRuntime.MIN_SUPPORTED_VERSION. Anything
# older is ignored by yt-dlp, so treating it as found would be a lie.
MIN_DENO = (2, 3, 0)

INSTALL_HINT = "winget install DenoLand.Deno --scope user   (or re-run Install.cmd)"

WHY = ("YouTube throttles downloads to roughly 1/50 speed without it: "
       "about 10 MiB, then a minute of nothing, over and over.")


def _version(exe):
    """(major, minor, patch) that `exe --version` reports, or None."""
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=20).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"deno\s+(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(g) for g in m.groups()) if m else None


def _candidates():
    yield ROOT / ".tools" / "deno.exe"
    # The official install script and `deno upgrade` both live here.
    yield Path(os.path.expanduser("~")) / ".deno" / "bin" / "deno.exe"
    # Where winget leaves a portable package. Whether it also gets a shim in
    # Links depends on whether Developer Mode is on, and either way a console
    # opened before the install is still holding the old PATH -- so look in
    # both places by hand rather than trusting PATH to have caught up.
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet"
        yield winget / "Links" / "deno.exe"
        for pkg in sorted(winget.glob("Packages/DenoLand.Deno*/deno.exe")):
            yield pkg
    # PATH last: it finds a winget or Scoop install, but on a fresh per-user
    # install this process may still be holding the PATH it started with.
    from shutil import which
    found = which("deno")
    if found:
        yield Path(found)


def find():
    """Path of a deno new enough for yt-dlp, as a string, or None."""
    seen = set()
    for path in _candidates():
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file():
            continue
        version = _version(path)
        if version and version >= MIN_DENO:
            return str(path)
    return None


def describe():
    """(path, version_text) of the runtime yt-dlp will use, or (None, None)."""
    path = find()
    if not path:
        return None, None
    version = _version(path)
    return path, ".".join(str(n) for n in version) if version else "unknown"
