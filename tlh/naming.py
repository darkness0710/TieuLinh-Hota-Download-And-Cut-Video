"""Name outputs `[DD-MM-YYYY] Stream.mp4` after the day the stream happened.

Downloads are named with the date in front -- `[23-08-2026] title [id].mp4` --
so the date travels with the file and survives clearing work/ or copying the
video elsewhere. A record in `work/index.json` and, failing that, the file
timestamp are the fallbacks, in that order.

The date is taken from `release_timestamp` converted to LOCAL time, not from
YouTube's `upload_date`, which is UTC. For a stream that starts late in the
evening the two agree; one that starts after midnight local is still the
previous day in UTC, and would be filed a day early.

The index also remembers which output each input produced. Without that,
re-running the same video and processing a different video from the same day
look identical, and one of them is wrong: the first should be skipped, the
second should become "(2)".
"""
import datetime
import json
import os
import re

INDEX_NAME = "index.json"
STREAM_LABEL = "Stream"


def _index_path(workroot):
    return os.path.join(workroot, INDEX_NAME)


def load_index(workroot):
    path = _index_path(workroot)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            index = json.load(fh)
    except Exception:
        return {}                               # unreadable: start over

    # Entries written before dates carried a source. Only record_download ever
    # stored the video id, so an entry that has one has a real YouTube date;
    # anything else is a guess and stays untrusted.
    for entry in index.values():
        if entry.get("date") and "date_source" not in entry:
            entry["date_source"] = "youtube" if entry.get("id") else "unknown"
    return index


def save_index(workroot, index):
    os.makedirs(workroot, exist_ok=True)
    with open(_index_path(workroot), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)


def record_download(workroot, filename, info):
    """Remember what YouTube said about a file we just downloaded."""
    index = load_index(workroot)
    entry = index.get(filename, {})
    date = date_from_info(info)
    entry.update({
        "title": info.get("title"),
        "id": info.get("id"),
        "webpage_url": info.get("webpage_url"),
        "date": date,
        "date_source": "youtube" if date else None,
    })
    index[filename] = entry
    save_index(workroot, index)
    return entry


def date_from_info(info):
    """DD-MM-YYYY for a yt-dlp info dict, in local time."""
    stamp = info.get("release_timestamp") or info.get("timestamp")
    if stamp:
        return datetime.datetime.fromtimestamp(stamp).strftime("%d-%m-%Y")
    raw = info.get("release_date") or info.get("upload_date")
    if raw and len(raw) == 8:
        return f"{raw[6:8]}-{raw[4:6]}-{raw[0:4]}"
    return None


DATE_IN_NAME = re.compile(r"^\[(\d{2})-(\d{2})-(\d{4})\]")


def date_in_filename(video):
    """`DD-MM-YYYY` read off the front of the filename, if it is there."""
    m = DATE_IN_NAME.match(os.path.basename(video))
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        datetime.date(year, month, day)         # reject 32-13-2026
    except ValueError:
        return None
    return f"{day:02d}-{month:02d}-{year:04d}"


def date_for(video, workroot, log=print):
    """The stream date for an input file, and where it came from.

    Three sources, best first. The filename wins because it is the only one
    that survives clearing work/ or copying the video to another machine --
    downloads are named with the date in front for exactly that reason.
    """
    from_name = date_in_filename(video)
    if from_name:
        return from_name, "filename"

    filename = os.path.basename(video)
    entry = load_index(workroot).get(filename)
    # Only a date that came from YouTube counts. A guess must never be written
    # into the index and read back as though it were a fact -- that is exactly
    # what happened before: output_name() stored the file-timestamp fallback,
    # and the next run reported it as a download record, uncertainty gone.
    if entry and entry.get("date") and entry.get("date_source") == "youtube":
        return entry["date"], "download record"

    stamp = os.path.getmtime(video)
    fallback = datetime.datetime.fromtimestamp(stamp).strftime("%d-%m-%Y")
    log(f"        no date in the filename and no download record, so dating "
        f"this {fallback} from the file timestamp -- which is wrong if the "
        f"file has ever been copied. Rename it to start with [DD-MM-YYYY] to "
        f"be sure.")
    return fallback, "mtime"


def _taken(outdir):
    if not os.path.isdir(outdir):
        return set()
    return {n for n in os.listdir(outdir) if n.lower().endswith(".mp4")}


def output_name(video, outdir, workroot, log=print):
    """`[DD-MM-YYYY] Stream.mp4`, numbered if that day already has one.

    Returns (path, already_done). `already_done` is True when this exact input
    has been rendered before, so the caller can skip it.
    """
    filename = os.path.basename(video)
    index = load_index(workroot)
    entry = index.get(filename, {})

    previous = entry.get("output")
    if previous and os.path.exists(os.path.join(outdir, previous)):
        return os.path.join(outdir, previous), True

    date, _source = date_for(video, workroot, log=log)
    # Names already handed to another input count as taken even when nothing
    # has been rendered yet. Checking only the folder gives two videos from the
    # same day the same name, and the second render overwrites the first.
    taken = _taken(outdir) | {
        e["output"] for name, e in index.items()
        if name != filename and e.get("output")}
    if previous:                                # ours, just not rendered yet
        taken.discard(previous)

    base = f"[{date}] {STREAM_LABEL}"
    candidate = f"{base}.mp4"
    n = 1
    while candidate in taken:
        n += 1
        candidate = f"{base} ({n}).mp4"

    # Only the output mapping is stored here. The date is deliberately not
    # written back: if it came from the file timestamp it is a guess, and
    # saving it would make the next run believe it.
    entry["output"] = candidate
    index[filename] = entry
    save_index(workroot, index)
    return os.path.join(outdir, candidate), False


def game_output_name(output_path, number, label="Opponent"):
    """`[DD-MM-YYYY] Opponent (game N).mp4`, from the whole-stream name.

    The date prefix and any "(2)" that marks a second stream from the same day
    are both carried over, so two streams on one day cannot produce two files
    called "game 1".
    """
    folder, name = os.path.split(output_path)
    stem = os.path.splitext(name)[0]
    match = DATE_IN_NAME.match(stem)
    prefix = f"{match.group(0)} " if match else ""
    # "[date] Stream (2)" -> the "(2)" belongs on the game files too.
    same_day = re.search(r"\((\d+)\)$", stem)
    tail = f" ({same_day.group(1)})" if same_day else ""
    return os.path.join(folder, f"{prefix}{label} (game {number}){tail}.mp4")


# A download ends in the YouTube id: "... [LCPHoRAiE18].mp4".
VIDEO_ID_SUFFIX = re.compile(r"\s*\[[A-Za-z0-9_-]{8,}\]$")


def clip_name(source, start, end, folder=None):
    """Name for a piece cut out of `source`, as a bare filename.

    Two rules, both learned the hard way:

    * KEEP the [DD-MM-YYYY] in front. date_for() reads the filename first, so
      the clip still knows which stream it came from after work/ is cleared.
    * DROP the [videoid] at the end. already_have() matches on that id and
      skips anything carrying it as a finished download -- so a clip left in
      input/ would answer for the whole VOD, and the next run of that link
      would "succeed" instantly with a fifteen-minute file.
    """
    stem, ext = os.path.splitext(os.path.basename(source))
    stem = VIDEO_ID_SUFFIX.sub("", stem).rstrip(" .")

    def stamp(v):
        v = max(0, int(v))
        return f"{v // 3600}h{v % 3600 // 60:02d}m{v % 60:02d}"

    base = f"{stem} ({stamp(start)}-{stamp(end)})"
    name = work_slug(base, limit=90) + (ext or ".mp4")
    if not folder:
        return name
    # Cutting the same range twice is a re-do, not a mistake, but it should
    # not overwrite what is already there while something may be reading it.
    n, out = 2, name
    while os.path.exists(os.path.join(folder, out)):
        out = work_slug(f"{base} ({n})", limit=90) + (ext or ".mp4")
        n += 1
    return out


def work_slug(stem, limit=60):
    """Folder name for one video's scratch, safe as a Windows directory.

    The truncation is what makes this delicate. Cutting a title at 60
    characters can land on a space, and Windows will not keep a directory
    name that ends in a space or a dot: os.makedirs quietly creates the name
    without it, while every path built afterwards still carries the space --
    so writing signal.npz into it fails with FileNotFoundError. That arrives
    four and a half minutes into a run, after the entire signal pass, which
    is the most expensive possible place to find out.
    """
    return stem[:limit].rstrip(" .") or "video"


def chapters_path(output_path):
    """Chapter list beside the video, sharing its name."""
    return re.sub(r"\.mp4$", ".txt", output_path, flags=re.I)
