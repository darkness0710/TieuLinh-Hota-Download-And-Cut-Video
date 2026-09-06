<#
    Offer two ways in -- fetch a YouTube link, or use whatever is already in
    input\ -- then cut, write the chapters, and say where everything went.

    Do not run this directly by double-clicking -- Windows opens .ps1 files in
    Notepad. Double-click Start.cmd in the folder above, which calls this.
#>
[CmdletBinding()]
param([string]$Url)

$ErrorActionPreference = "Stop"
# This script lives in scripts\, so the project root is one level up.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

function Line { Write-Host ("-" * 66) -ForegroundColor DarkGray }
function GB($bytes) { "{0,7:N2} GiB" -f ($bytes / 1GB) }

function Hold {
    # Read-Host returns instantly if a newline is still sitting in the input
    # buffer -- a second tap on Enter at the menu is enough -- and then the
    # last thing printed vanishes with the window before it can be read. Drop
    # whatever is buffered first, so this always waits for a fresh keypress.
    try { $Host.UI.RawUI.FlushInputBuffer() } catch { }
    Read-Host "  Press Enter to close" | Out-Null
}

# Any terminating error otherwise closes the window on the spot, taking the
# message with it. A trap needs no try block wrapped round the whole script.
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

function Show-Drive {
    # A download plus its render wants tens of gigabytes. Show what is left
    # before starting, so a full disk is obvious now rather than an hour in.
    $drive = [System.IO.Path]::GetPathRoot((Get-Location).Path)
    $d = Get-PSDrive -PSProvider FileSystem |
         Where-Object { $_.Root -eq $drive } | Select-Object -First 1
    if (-not $d) { return }
    $total = $d.Used + $d.Free
    if ($total -le 0) { return }
    $pct = [int](100 * $d.Free / $total)
    $bar = "#" * [int]((100 - $pct) / 4) + "-" * [int]($pct / 4)
    Write-Host ""
    Write-Host ("  Drive {0}  [{1}]" -f $drive, $bar)
    Write-Host ("    used {0}   free {1}   of {2}   ({3}% free)" -f `
        (GB $d.Used), (GB $d.Free), (GB $total), $pct) -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Tieulinh HOTA - cut a stream VOD" -ForegroundColor Cyan
Write-Host "  Author: Nguyễn Thanh Hải" -ForegroundColor DarkGray
Line
Show-Drive

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
    Write-Host "  (using system Python; Install.cmd would make a .venv)" -ForegroundColor DarkYellow
}

# A URL passed on the command line skips the menu.
$mode = if ($Url) { "1" } else { $null }

$pending = @()
if (Test-Path (Join-Path $root "input")) {
    # @() around it: an empty pipeline assigns $null, and $null.Count is not
    # 0, so the "input\ is empty" guard below would be walked straight past.
    $pending = @(Get-ChildItem (Join-Path $root "input") -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".mp4", ".mkv", ".ts", ".flv", ".mov", ".webm", ".avi") })
}

while (-not $mode) {
    Write-Host ""
    Write-Host "  What do you want to do?"
    Write-Host ""
    Write-Host "    1  Download from a YouTube link, then cut it"
    if ($pending.Count -eq 1) {
        Write-Host ("    2  Cut the video already in input\  ({0} file)" -f $pending.Count)
    } else {
        Write-Host ("    2  Cut the videos already in input\  ({0} files)" -f $pending.Count)
    }
    Write-Host "    0  Cancel"
    Write-Host ""
    $mode = (Read-Host "  Choose").Trim()
    if ($mode -eq "0") {
        Write-Host ""
        Write-Host "  Cancelled." -ForegroundColor Green
        Write-Host ""
        Hold
        exit 0
    }
    if ($mode -notin @("1", "2")) {
        Write-Host "  Type 1, 2 or 0." -ForegroundColor Yellow
        $mode = $null
    }
}

$runArgs = @()
if ($mode -eq "1") {
    while (-not $Url) {
        Write-Host ""
        $Url = (Read-Host "  Paste the YouTube URL").Trim()
        if (-not $Url) { Write-Host "  Nothing entered." -ForegroundColor Yellow }
    }
    Write-Host ""
    Write-Host "  Reading the link..." -ForegroundColor DarkGray
    Write-Host "  The real size and duration are shown before the download starts." -ForegroundColor DarkGray
    $runArgs = @("--url", $Url, "--live-progress")
} else {
    if ($pending.Count -eq 0) {
        Write-Host ""
        Write-Host "  input\ has no finished video. Put files there, or choose 1 to download one." -ForegroundColor Yellow
        $halves = @(Get-ChildItem (Join-Path $root "input") -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "\.(part|ytdl|temp)$|\.part-Frag\d+$" })
        if ($halves) {
            $bytes = ($halves | Measure-Object -Property Length -Sum).Sum
            Write-Host ""
            Write-Host ("  There is an unfinished download here ({0}):" -f (GB $bytes).Trim()) -ForegroundColor Cyan
            Write-Host ("    {0}" -f ($halves[0].Name -replace "\.f\d+\.mp4.*$", "")) -ForegroundColor DarkGray
            Write-Host "  Choose 1 and paste the same link to carry on from there." -ForegroundColor Cyan
        }
        Write-Host ""
        Hold
        exit 0
    }

    # Never start on the whole folder without being asked. Each video costs
    # most of an hour, so "all" on a folder of a hundred is days of work
    # nobody meant to begin.
    $chosen = $pending
    if ($pending.Count -gt 1) {
        Write-Host ""
        Write-Host ("  {0} videos in input\:" -f $pending.Count)
        Write-Host ""
        for ($i = 0; $i -lt $pending.Count; $i++) {
            Write-Host ("    {0,3}  {1,7:N2} GiB  {2}" -f ($i + 1),
                ($pending[$i].Length / 1GB), $pending[$i].Name)
        }
        Write-Host ""
        Write-Host "  Pick one or more numbers (like 1 or 1,3), or type all." -ForegroundColor DarkGray
        while ($true) {
            $answer = (Read-Host "  Which").Trim()
            if (-not $answer) { continue }
            if ($answer -eq "0") {
                Write-Host ""
                Write-Host "  Cancelled." -ForegroundColor Green
                Write-Host ""
                Hold
                exit 0
            }
            if ($answer -match '^(?i)all$') { $chosen = $pending; break }
            $picked = @()
            $bad = $false
            foreach ($piece in ($answer -split '[,\s]+' | Where-Object { $_ })) {
                if ($piece -notmatch '^\d+$') { $bad = $true; break }
                $n = [int]$piece
                if ($n -lt 1 -or $n -gt $pending.Count) { $bad = $true; break }
                $picked += $pending[$n - 1]
            }
            if ($bad -or -not $picked) {
                Write-Host "  Use numbers from the list, or all, or 0 to cancel." -ForegroundColor Yellow
                continue
            }
            $chosen = $picked | Select-Object -Unique
            break
        }
    }

    Write-Host ""
    Write-Host ("  Processing {0} video(s):" -f @($chosen).Count) -ForegroundColor DarkGray
    foreach ($f in @($chosen)) {
        Write-Host ("    {0,7:N2} GiB  {1}" -f ($f.Length / 1GB), $f.Name) -ForegroundColor DarkGray
        $runArgs += @("--file", $f.Name)
    }
    Write-Host ""
    Write-Host "  Anything already rendered is skipped." -ForegroundColor DarkGray
}

Line
Write-Host ""
$started = Get-Date
Write-Host ("  Started at {0:HH:mm:ss}" -f $started) -ForegroundColor DarkGray
Write-Host ""

# The elapsed clock is printed by the Python side, on the same lines as the
# download bar and the render counter. Running it as a background job here so
# PowerShell could tick a clock of its own would break the download bar, which
# redraws one line with carriage returns rather than emitting whole lines.
& $python "run.py" @runArgs
$code = $LASTEXITCODE
$elapsed = (Get-Date) - $started

Line
if ($code -eq 0) {
    Write-Host ("  Finished in {0:hh\:mm\:ss}" -f $elapsed) -ForegroundColor Green
    Write-Host "  Paste the .txt next to the video into the YouTube description."
} else {
    Write-Host "  Something failed (exit $code). The messages above say what." -ForegroundColor Red
}
Write-Host ""
Hold
exit $code
