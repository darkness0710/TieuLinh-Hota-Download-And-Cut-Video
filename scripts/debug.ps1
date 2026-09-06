<#
    Analyse ONE video already in input\ and leave the cut pieces where they
    can be watched, without joining them into a finished file.

    Start.cmd concatenates: it renders every kept stretch into
    work\<name>\parts\ and then joins those into one file in output\, deleting
    the pieces afterwards. For judging what the detector decided, the pieces
    are the better answer -- one file per kept stretch, so a wrong cut is one
    file you open rather than a timestamp you go hunting for -- and the joined
    file is a second copy of the same footage. So this runs run.py
    --parts-only against one file you pick rather than the folder.

    Two speeds:
      debug.cmd              analyse, render the pieces, stop before joining
      debug.cmd -NoRender    analyse only: segments.csv and chapters.txt

    The signal is cached in work\<name>\signal.npz, so a second run on the
    same file skips the decode entirely and re-derives the segments from the
    cache in seconds. That is the loop to iterate a threshold in. Pass
    -Reanalyse when it is the signal itself you have changed.

    Do not run this directly by double-clicking -- Windows opens .ps1 files in
    Notepad. Double-click debug.cmd in the folder above, which calls this.
#>
[CmdletBinding()]
param([string]$File, [switch]$Reanalyse, [switch]$NoRender)

$ErrorActionPreference = "Stop"
# This script lives in scripts\, so the project root is one level up.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

function Line { Write-Host ("-" * 66) -ForegroundColor DarkGray }

function Hold {
    # Read-Host returns instantly if a newline is still sitting in the input
    # buffer -- a second tap on Enter at the menu is enough -- and then the
    # last thing printed vanishes with the window before it can be read.
    try { $Host.UI.RawUI.FlushInputBuffer() } catch { }
    Read-Host "  Press Enter to close" | Out-Null
}

# Any terminating error otherwise closes the window on the spot, taking the
# message with it.
trap {
    Write-Host ""
    Write-Host "  Something went wrong:" -ForegroundColor Red
    Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
    if ($_.InvocationInfo) {
        Write-Host ("    at line {0}" -f $_.InvocationInfo.ScriptLineNumber) -ForegroundColor DarkGray
    }
    Write-Host ""
    Hold
    exit 1
}

Write-Host ""
if ($NoRender) {
    Write-Host "  Tieulinh HOTA - analyse only, no render" -ForegroundColor Cyan
} else {
    Write-Host "  Tieulinh HOTA - cut into pieces, do not join them" -ForegroundColor Cyan
}
Write-Host "  Author: Nguyễn Thanh Hải" -ForegroundColor DarkGray
Line

# The venv built by setup.ps1 is preferred; a plain python is a fallback so the
# script still works if someone installed the dependencies globally.
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if (-not $found) {
        Write-Host ""
        Write-Host "  No Python found." -ForegroundColor Red
        Write-Host "  Double-click Install.cmd first." -ForegroundColor Yellow
        Write-Host ""
        Hold
        exit 1
    }
    $python = $found.Source
}

# @() around it: an empty pipeline assigns $null, and $null.Count is not 0, so
# the guard below would be walked straight past.
$videos = @(Get-ChildItem (Join-Path $root "input") -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".mp4", ".mkv", ".ts", ".flv", ".mov", ".webm", ".avi") } |
    Sort-Object Name)

if ($videos.Count -eq 0) {
    Write-Host ""
    Write-Host "  input\ has no video in it. Put one there, or use Start.cmd to download one." -ForegroundColor Yellow
    Write-Host ""
    Hold
    exit 0
}

# A name passed on the command line skips the menu, so this can be scripted.
$chosen = $null
if ($File) {
    $chosen = $videos | Where-Object { $_.Name -eq $File } | Select-Object -First 1
    if (-not $chosen) {
        Write-Host ""
        Write-Host "  input\ has no file named exactly:" -ForegroundColor Red
        Write-Host "    $File" -ForegroundColor Red
        Write-Host ""
        Hold
        exit 1
    }
}

# One file, never the folder: analysing a folder of VODs is what Start.cmd is
# for, and doing it by accident is half an hour a piece.
while (-not $chosen) {
    Write-Host ""
    Write-Host ("  {0} video(s) in input\:" -f $videos.Count)
    Write-Host ""
    for ($i = 0; $i -lt $videos.Count; $i++) {
        Write-Host ("    {0,3}  {1,7:N2} GiB  {2}" -f ($i + 1),
            ($videos[$i].Length / 1GB), $videos[$i].Name)
    }
    Write-Host ""
    Write-Host "    0  Cancel"
    Write-Host ""
    $answer = (Read-Host "  Which one (a single number)").Trim()
    if ($answer -eq "0") {
        Write-Host ""
        Write-Host "  Cancelled." -ForegroundColor Green
        Write-Host ""
        Hold
        exit 0
    }
    if ($answer -notmatch '^\d+$') {
        Write-Host "  One number from the list, or 0 to cancel." -ForegroundColor Yellow
        continue
    }
    $n = [int]$answer
    if ($n -lt 1 -or $n -gt $videos.Count) {
        Write-Host "  There is no $n in the list." -ForegroundColor Yellow
        continue
    }
    $chosen = $videos[$n - 1]
}

$runArgs = @(if ($NoRender) { "--dry-run" } else { "--parts-only" })
$runArgs += @("--file", $chosen.Name)
if ($Reanalyse) { $runArgs += "--reanalyse" }

Write-Host ""
Write-Host ("  Analysing  {0}" -f $chosen.Name)
Write-Host ("  Size       {0,7:N2} GiB" -f ($chosen.Length / 1GB)) -ForegroundColor DarkGray
if ($Reanalyse) {
    Write-Host "  Signal     decoding again (-Reanalyse)" -ForegroundColor DarkGray
} else {
    Write-Host "  Signal     reusing work\<name>\signal.npz if it is there" -ForegroundColor DarkGray
    Write-Host "             (pass -Reanalyse to decode the video again)" -ForegroundColor DarkGray
}
if ($NoRender) {
    Write-Host "  Render     skipped -- segment list only (-NoRender)" -ForegroundColor DarkGray
} else {
    Write-Host "  Render     one mp4 per kept stretch, into work\<name>\parts" -ForegroundColor DarkGray
    Write-Host "             not joined, nothing written to output\" -ForegroundColor DarkGray
}
Line
Write-Host ""
$started = Get-Date
& $python "run.py" @runArgs
$code = $LASTEXITCODE
$elapsed = (Get-Date) - $started

Line
if ($code -eq 0) {
    Write-Host ("  Finished in {0:hh\:mm\:ss}" -f $elapsed) -ForegroundColor Green
    # run.py prints the path as it writes it, but it scrolls away behind the
    # progress lines, and every follow-up command needs it.
    $csv = Get-ChildItem (Join-Path $root "work") -Recurse -Filter segments.csv -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($csv) {
        $dir = Split-Path -Parent $csv.FullName
        $rel = $dir.Substring($root.Length).TrimStart('\')
        $parts = @(Get-ChildItem (Join-Path $dir "parts") -Filter *.mp4 -ErrorAction SilentlyContinue)
        if ($parts.Count -gt 0) {
            $bytes = ($parts | Measure-Object -Property Length -Sum).Sum
            Write-Host ""
            Write-Host ("  {0} piece(s), {1,7:N2} GiB:" -f $parts.Count, ($bytes / 1GB))
            Write-Host ("    {0}\parts\" -f $rel)
            Write-Host "  Watch them in order; a wrong cut is one file, not a timestamp." -ForegroundColor DarkGray
        }
        Write-Host ""
        Write-Host "  Segment list:"
        Write-Host ("    {0}\segments.csv" -f $rel)
        Write-Host ("    {0}\segments.json" -f $rel)
        Write-Host ""
        Write-Host "  To check it:" -ForegroundColor DarkGray
        Write-Host ("    .venv\Scripts\python.exe tools\qc.py labels -s ""{0}\segments.json""" -f $rel) -ForegroundColor DarkGray
        Write-Host ("    .venv\Scripts\python.exe tools\qc.py cuts ""input\{0}"" -s ""{1}\segments.json""" -f $chosen.Name, $rel) -ForegroundColor DarkGray
    }
} else {
    Write-Host "  Something failed (exit $code). The messages above say what." -ForegroundColor Red
}
Write-Host ""
Hold
exit $code
