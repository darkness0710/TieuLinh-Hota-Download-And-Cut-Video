# tieu_linh_hota

**Author:** Nguyễn Thanh Hải

Trims a Tieulinh HOTA stream VOD down to the parts that are actually being
played, joins the pieces with a fade to black, and writes a YouTube chapter list
naming the in-game day. On the reference VOD (2:48:19) that leaves
**1:50:17 (65.5%)**, removes **58:02** of dead time, and produces **56
chapters**.

## Click these

| | |
|---|---|
| **`Install.cmd`** | once, when setting up. No administrator rights needed |
| **`Start.cmd`** | every time: asks for a URL or uses `input/`, cuts, writes `output/` |
| **`debug.cmd`** | one file, analysis only or pieces only — for testing the detector |
| **`web.cmd`** | a local page: paste a link, see which stage each job is in |
| **`Clear.cmd`** | free disk space, with confirmation, via the Recycle Bin |

Everything else is machinery; nothing needs editing by hand except
`tlh/config.py`.

`Start.cmd` offers two routes — download a link, or use what is already in
`input/`. With several videos it lists them numbered and asks which: one,
`1,3`, or `all`. It never starts on a whole folder unasked, because each video
costs most of an hour.

### debug.cmd has two speeds

| | what runs | on a 30 min clip |
|---|---|---|
| `debug.cmd` | analysis, then one mp4 per kept stretch into `work/<name>/parts/`, **not joined** | ~7 min |
| `debug.cmd -NoRender` | analysis only: `segments.csv`, `segments.json`, `chapters.txt` | ~2.4 min |

Add `-Reanalyse` to decode the video again instead of reusing
`work/<name>/signal.npz`. Both modes take one file, never the folder, and
neither writes anything to `output/`.

### web.cmd, for whoever is not reading a console

Opens `http://127.0.0.1:8765`. Paste a link and start it, watch the stage and
percentage of every job, re-run a file from `input/`, see what is left on the
drive. Job records live in `work/jobs/` and survive the window closing, which
is the one question a console cannot answer afterwards: *has it finished?*

Leave the black window open — the jobs are its child processes. Jobs started
from `Start.cmd` do not appear on the page. Details in
[documents/web.md](documents/web.md).

## Commands

```
python run.py                           # everything in input/ -> output/
python run.py --url https://youtu.be/X  # download into input/, then cut it
python run.py --urls links.txt          # a list of URLs, one per line
python run.py --file "exact name.mp4"   # exactly this file (repeatable)
python run.py --only "match1*.mp4"      # files matching a glob (repeatable)
python run.py -i D:\vods -o D:\cut      # different folders
```

| option | |
|---|---|
| `--dry-run` | analyse and write the segment list, no render |
| `--parts-only` | render the pieces into `work/<name>/parts`, do not join them |
| `--per-game` | one video per game, `[DD-MM-YYYY] Opponent (game N).mp4`, instead of one for the whole stream |
| `--keep-parts` | join them, but keep the pieces too |
| `--force` | re-render even if the output already exists |
| `--reanalyse` | ignore the cached signal and decode again |
| `--live-progress` | one redrawing download progress line instead of many |
| `--workers N` | parallel decoders for the analysis (default 4) |
| `--render-workers N` | parallel hardware encoders (default 3) |

Use `--file`, not `--only`, for a downloaded name: those contain `[brackets]`,
which a glob reads as a character class matching nothing.

A file whose output already exists is skipped, so an interrupted batch can just
be restarted. A file that fails is reported and the batch carries on.

## Names

Everything is named after the day the stream happened, and the date leads the
filename at both ends so it travels with the file:

```
input/[23-08-2026] Live ngan mai off Elephant 1y [U197AGXIO3s].mp4
  ->  output/[23-08-2026] Stream.mp4
      output/[23-08-2026] Stream.txt      <- chapters, paste into the description
```

A second stream from the same day becomes `[23-08-2026] Stream (2).mp4`. The
date is read, in order, from the `[DD-MM-YYYY]` on the front of the input
filename, then the download record in `work/index.json`, and only failing both
from the file's timestamp, with a warning.

Downloads ask for 1080p60 H.264 and warn if what arrives is not 1920x1080 —
every overlay coordinate assumes 1080p, so another size would produce a
confidently wrong cut.

## Layout

```
Install.cmd  Start.cmd  debug.cmd  web.cmd  Clear.cmd     what to double-click
scripts/
  setup.ps1             what Install.cmd runs
  download_and_cut.ps1  what Start.cmd runs
  debug.ps1             what debug.cmd runs
  clear.ps1             what Clear.cmd runs
run.py                  entry point: input/ -> output/
tlh/
  config.py             every coordinate and threshold  <-- the only file to
                        change if a VOD uses a different overlay
  ffmpeg.py             ffmpeg location, duration, frame helpers
  encoder.py            probes NVENC / QuickSync / AMF / libx264
  fetch.py              yt-dlp download, 1080p60 H.264 + AAC
  jsruntime.py          finds deno, without which YouTube throttles downloads
  aria2.py              finds aria2c, the multi-connection downloader
  web.py                the local web server: spawns run.py, tracks jobs
  webpage.py            the single page it serves
  naming.py             [DD-MM-YYYY] Stream.mp4, and the download record
  signal.py             pass 1: clocks, seat, day counter, Spell Points panels
  daycount.py           reads "Month: M, Week: W, Day: D"
  screens.py            pass 2/3: dead-screen templates, map-vs-combat test
  segments.py           the keep/cut rule
  timeline.py           chapters
  render.py             fades, black holds, encode, concat
  process.py            runs the above for one video
templates/              reference crops, needed at runtime -- do not delete
tools/
  make_templates.py     rebuild the templates from a VOD
  inspect_frames.py     probe / coordinate grid / contact sheet / zoom / clocks
  qc.py                 check a cut: cuts / fades / labels
  labels_reference.csv  24 hand-checked timestamps, the regression net
  labels_bulwark.csv    a second net, from a second VOD
input/  output/  work/  data (git-ignored)
```

## Details

| | |
|---|---|
| [documents/setup.md](documents/setup.md) | installing, moving to another machine, what to do when it fails |
| [documents/cutting-rule.md](documents/cutting-rule.md) | what gets cut, and eleven reasons the obvious rule is wrong |
| [documents/chapters.md](documents/chapters.md) | the day counter, splitting games, marking battles |
| [documents/checking.md](documents/checking.md) | qc.py, the two regression nets, adapting to a different overlay |
| [documents/downloading.md](documents/downloading.md) | why deno and aria2c, and the per-connection cap they work around |
| [documents/cost.md](documents/cost.md) | measured times per stage, and what does not speed them up |
| [documents/web.md](documents/web.md) | the local page: what it answers, how it is built, what it does not do |
