# The web page

```
web.cmd                     opens http://127.0.0.1:8765 in a browser
python -m tlh.web           the same, without opening one
python -m tlh.web --port N  a different port
```

For the people who use this tool but do not read a console. It answers the
questions the console cannot answer once its window is closed:

| question | where the answer comes from |
|---|---|
| which stage is this link in? | the job's `stage` badge |
| has it finished downloading? | `downloading` -> `analysing` |
| has it been analysed and cut? | `rendering` -> `Xong`, with the output path and size |
| how much disk is left? | the drive bar, and a size per file |
| can I run a file from `input/` again? | one row per file, a Run button |
| what did the channel stream, and what is the link? | **Chọn từ kênh…** beside the link box |
| can I try the detector on fifteen minutes instead of four hours? | the **Hỗ trợ cắt ghép** tab |
| can I delete a download I no longer want? | a Delete button per file, straight to the Recycle Bin |
| when did this run, and how long did it take? | a timestamp line on every job card |

## Two tabs

**Chức năng** is the whole pipeline: pick a job, pick a source, watch it run.
**Hỗ trợ cắt ghép** cuts a range out of a video already in `input/`. The drive
bar and the folder sizes sit above both, because they matter to both.

It cuts; it does not join. Joining pieces is a different problem and the
pipeline already does the joining that matters.

### Why it exists, and why it needs byte ranges

Testing a detector change against a four-hour VOD costs an hour of analysis.
Against fifteen minutes it costs four. Every fix in this project so far was
checked on a clip cut by hand from the command line, which is the argument for
having it in the page.

The preview is the reason `GET /media` exists, and it is the only endpoint that
serves file *contents* rather than facts about them. It answers **HTTP byte
ranges**, and that is not a detail: without `Accept-Ranges` a `<video>` has to
read from byte zero to reach two hours into a 7 GiB file, so seeking never
arrives. With ranges a seek is one request for one megabyte. Measured against
a 2.69 GB clip: head, middle and tail ranges all return byte-exact content,
`bytes=-512` returns the last 512 bytes, an out-of-range ask gets 416, and
`..%2F..%2F` gets 404 -- the filename must be a bare basename that exists in
`input/` and looks like a video, the same rule `/api/jobs` uses.

### Marks come off the player

`Đặt tại đây` reads `video.currentTime`. Typing a timestamp is what a command
line is for; the value of a preview is seeing the frame and taking the time
off it. The fields still accept `1:02:03`, `2:03`, `90` or `0h10m15` for
adjusting by hand.

### The clip's name is not cosmetic

`naming.clip_name()` keeps the `[DD-MM-YYYY]` in front and **drops the
`[videoid]`** at the end. Both matter:

* `date_for()` reads the filename first, so the clip still knows its stream
  date after `work/` is cleared;
* `already_have()` matches on that id and treats anything carrying it as a
  finished download -- so a clip left in `input/` would answer for the whole
  VOD, and the next run of that link would "succeed" instantly with a
  fifteen-minute file. That is the same failure as the `.f299.mp4` one in
  documents/downloading.md, invited on purpose instead of by accident.

### Stream copy, and what that costs

`-c copy`, no re-encode: ninety minutes in seconds, original pixels. In
exchange `-ss` lands on the keyframe at or before the mark, so a clip runs
longer than asked -- measured, 15 seconds requested came back 21. The panel
says so, and the result line reports the real length rather than the requested
one. For cutting a test piece down to something quick to run, none of that
matters; for anything frame-accurate, it would.

## Picking a link off the channel

**Chọn từ kênh…**, next to the link box, lists the newest 10 / 20 / 100
livestreams of either channel -- the main one and the backup -- with a
thumbnail, a length, a view count and a Copy link button.

The listing is *flat*: yt-dlp is told not to open each video's player API, so a
hundred rows cost one request and about a second, and no JavaScript runtime is
needed. The price of that is the date, which a flat entry does not carry: it is
one request per video, so it is fetched only for a row somebody presses **Ngày
phát** on.

Which also means the picker is for browsing, not for finding one date: a
hundred rows only reach a few months back, and the channel has over a thousand
streams. Looking up an older date is a binary search over the flat listing --
the dates are monotonic, so about a dozen lookups cover the lot.

Leave the console window open: the jobs are child processes of the server.

Closing it stops them, and that is guaranteed rather than hoped for. Every
child is put in a Windows **job object** with `KILL_ON_JOB_CLOSE`, so the
kernel kills the whole tree when the last handle to the job goes away, which
happens when the server dies however it dies. Measured before that was added:
killing the server without letting it clean up left both `run.py` and its
ffmpeg grandchild running, burning CPU and bandwidth with no interface left to
stop them. Ctrl+C is handled explicitly as well, which stops things in order
and says so.

Data survives either way. A part-finished download leaves `.part`,
`.part-FragNN` or `.part.aria2` behind and the next run resumes from them; a
half-written piece under `parts/` is simply rendered again; and `signal.npz` is
written only once a whole signal pass has finished, so there is no such thing
as half a cache.

## How it is built

Three choices, all made to keep a working pipeline out of harm's way.

**Standard library only.** `http.server` and `subprocess`, no FastAPI, no
uvicorn, nothing added to `requirements.txt`. A page is not worth another
dependency that can fail to install on a machine where the whole point was to
install as little as possible.

**Nothing in the pipeline changed.** The server spawns `run.py` as a
subprocess and reads its output; it does not import the pipeline or reach
inside it. So the page cannot break a cut, and `Start.cmd` keeps working
exactly as before.

**127.0.0.1 only.** This endpoint starts processes. It never binds 0.0.0.0, a
URL has to be `http`/`https`, a filename has to be a bare name that already
exists in `input/`, and nothing is passed through a shell.

## What it costs

The server reads its child's stdout and matches it against the patterns in
`PATTERNS` (`tlh/web.py`) — it parses our own console output. Two consequences
worth knowing:

* If a progress line's wording changes, the page shows the stage but loses the
  percentage. It does not crash, and the log view still shows everything.
* Both the download bar and aria2c's readout redraw one line with a carriage
  return and never send a newline, so the reader splits on `\r` as well as
  `\n`. A plain line iterator would show nothing at all for the length of a
  download.

**Jobs started from `Start.cmd` are invisible here**, because the server only
knows about processes it started itself.

## State

One file per job under `work/jobs/`:

```
work/jobs/<id>.json     the record the page reads
work/jobs/<id>.log      everything the run printed, for the details view
```

Written atomically (temp file, then replace), because the page may read at any
moment. They outlive the server: on startup it loads them again, and any job
left mid-flight is marked `interrupted` rather than left showing a progress bar
frozen at 41% for ever.

## Honest progress

A smooth bar is more convincing than a line of text, so it has to be more
careful about lying. Four rules, each of them learned the hard way:

1. Speed is a trailing average, never the instantaneous figure. A bar once
   read "11.2 MiB/s, 9 minutes left" for a job that took ten hours, because it
   was quoting the burst that had just ended.
2. Every record carries when it was last updated, so the page can say "no new
   data for 40s". A bar that has stopped moving and an application that has
   hung are indistinguishable otherwise.
3. A download is two downloads — video, then audio. Going to 100% and starting
   again at 0% looks broken unless the page says why.
4. Per-stage percentages, labelled by stage. "analysis 100%" followed by
   "render 0%" reads as a restart.

## What it does not do

* No splitting per *opponent*. Splitting per **game** exists -- the second
  option on the page -- but the pipeline deliberately never reads player
  names, so two games against the same person come out as two videos rather
  than one. See [chapters.md](chapters.md).
* Nothing that lists a channel. Links are pasted one at a time; there is no
  picker for a channel's recent streams.
* No timezones. The timestamps on a card are this machine's local clock.
* No queue. Press start twice and two runs compete for the same CPU and the
  same bandwidth.
* No authentication. It is a page on your own machine, for you.
