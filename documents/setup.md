# Setting up on a new machine

**Author:** Nguyễn Thanh Hải

Windows 10 or 11. **No administrator rights are needed.**

Both are supported. Everything here runs on **Windows PowerShell 5.1**, which
ships with Windows 10 and 11 alike -- nothing needs PowerShell 7. The `.cmd`
launchers switch the console to UTF-8 (`chcp 65001`) before starting, because a
Windows 10 console is often codepage 437 or 1252 and would otherwise render the
Vietnamese text as rubbish.

Every dependency is a pip package, and ffmpeg travels inside `imageio-ffmpeg`,
so nothing touches PATH, the registry or Program Files. Everything lands in a
`.venv` folder beside the project.

---

## 1. Python

Needs **Python 3.10 or newer**. Check:

```powershell
py -3 --version
```

If it is missing, install it **per-user**, which also avoids admin:

```powershell
winget install Python.Python.3.12 --scope user
```

`winget` ships with Windows 11 but is not always there on Windows 10 -- it
arrives with App Installer from the Store, and a freshly imaged machine often
has neither. If the command is not found, use python.org instead and tick
**"Install for me only"** rather than *for all users*, which is the option that
asks for admin.

This is the only step that could ever need admin, and only if you choose a
system-wide install.

## 2. Copy the project

Copy the whole folder. These parts are **required at runtime** and must come
with it:

| folder | why |
|---|---|
| `tlh/` | the code |
| `templates/` | reference crops the detector matches against |
| `tools/` | QC and template rebuilding |
| `scripts/` | the installer and the launcher script |

These are safe to leave behind — they are rebuilt automatically:

| folder / file | |
|---|---|
| `.venv/` | rebuilt by setup |
| `.encoder.json` | re-probed on first render |
| `work/` | per-video scratch and the signal cache |
| `work/index.json` | which input produced which output. Losing it means a re-run renders a duplicate instead of skipping, so `Clear.cmd` leaves it alone. |
| `input/`, `output/` | your videos |

## 3. Run setup

Double-click **`Install.cmd`**.

It checks Python, builds `.venv`, installs `requirements.txt`, creates
`input/ output/ work/`, and runs a self test that confirms the templates are
present and reports which video encoder the machine has.

`Install.cmd` is a two-line launcher: Windows opens `.ps1` files in Notepad when
double-clicked, so the clickable file has to be a `.cmd`. It calls
`scripts\setup.ps1` with the execution policy bypassed **for that one process
only** -- nothing about the machine's policy is changed.

To rebuild the virtual environment from scratch:
`powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Force`

Expected output:

```
[1/5] Python
  OK    found Python 3.12 via 'py -3'
[2/5] virtual environment
  OK    created .venv
[3/5] dependencies
  OK    installed from requirements.txt
[4/5] folders
  OK    input/
  OK    output/
  OK    work/
[5/5] self test
  OK    numpy 2.5.2
  OK    opencv 5.0.0
  OK    ffmpeg 7.1
  OK    yt-dlp 2026.08.19
  OK    templates present
  OK    video encoder: h264_qsv
```

## 4. Use it

Double-click **`Start.cmd`**. It asks what you want to do:

```
    1  Download from a YouTube link, then cut it
    2  Cut the videos already in input    0  Cancel
```

Choose 1 and paste the link, or drop video files into `input\` yourself and
choose 2. Downloads are saved as `[DD-MM-YYYY] title [id].mp4`, with the stream
date in front so it stays with the file.

`Clear.cmd` frees disk space when it runs low. It shows what is there with
sizes, asks which group, then asks you to type `DELETE`, and sends everything to
the Recycle Bin. A `.part` file is an unfinished download, not rubbish -- running
`Start.cmd` on the same link resumes from it.

Windows opens `.ps1` files in Notepad when double-clicked, which is why the
clickable file is a `.cmd`; it just calls `scripts\download_and_cut.ps1`.

Or from a terminal:

```powershell
.venv\Scripts\python.exe run.py --url https://youtu.be/XXXXXXXXXXX
.venv\Scripts\python.exe run.py                 # everything already in input\
.venv\Scripts\python.exe run.py --dry-run       # analyse only, no render
```

---

## The encoder

Rendering uses whatever hardware the machine has. On the first render the
encoders are probed **by actually encoding a couple of frames** — ffmpeg lists
encoders it cannot open, so listing is not a test — and the winner is cached in
`.encoder.json`:

| order | encoder | |
|---|---|---|
| 1 | `h264_nvenc` | NVIDIA, fastest |
| 2 | `h264_qsv` | Intel QuickSync |
| 3 | `h264_amf` | AMD |
| 4 | `libx264` | software, always works, roughly 3x slower |

Nothing is hardcoded, so an AMD machine or one with an NVIDIA card works
unchanged. If it falls back to `libx264`, setup says so.

Measured on the development machine (i5-13420H, Intel UHD): NVENC absent, AMF
absent, QuickSync working.

## If something fails

**"no Python 3.10+ found"** — install Python per-user as in step 1, then
double-click `Install.cmd` again.

**Self test says templates missing** — `templates/` did not come across in the
copy. It is small and required; copy it.

**Self test warns about `libx264`** — the machine has no usable hardware
encoder. It still works, rendering is about 3x slower.

**Downloads fail** — check `yt-dlp` is installed (the self test reports it) and
that the URL is a finished VOD, not a stream still running. A live stream is
refused on purpose.

**The cut looks wrong on a new VOD** — the detector assumes a 1920x1080 frame
and a fixed overlay layout. `run.py` warns when the clock overlay is found in
under 20% of samples. See the last section of `README.md` for re-deriving the
coordinates.
