<#
    Free up disk space, with a look before the leap.

    This deletes video files -- hours of downloading and rendering -- so it
    shows what it is about to remove and how big it is, asks which group, and
    then asks again. Everything goes to the Recycle Bin, not straight out, so a
    misclick is recoverable.

    Do not run this directly by double-clicking -- Windows opens .ps1 files in
    Notepad. Double-click Clear.cmd in the folder above, which calls this.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
# This script lives in scripts\, so the project root is one level up.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

Add-Type -AssemblyName Microsoft.VisualBasic

function Line { Write-Host ("-" * 66) -ForegroundColor DarkGray }
function GB($bytes) { "{0,7:N2} GiB" -f ($bytes / 1GB) }

function Measure-Set($paths) {
    $files = @($paths | Where-Object { $_ } | ForEach-Object { $_ })
    $bytes = 0
    foreach ($f in $files) { $bytes += $f.Length }
    [pscustomobject]@{ Files = $files; Count = $files.Count; Bytes = $bytes }
}

function Get-Parts {
    if (-not (Test-Path "input")) { return @() }
    Get-ChildItem "input" -File -Filter "*.part" -ErrorAction SilentlyContinue
}
function Get-InputVideos {
    if (-not (Test-Path "input")) { return @() }
    Get-ChildItem "input" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -ne ".part" }
}
function Get-Output {
    if (-not (Test-Path "output")) { return @() }
    Get-ChildItem "output" -File -Recurse -ErrorAction SilentlyContinue
}
function Get-Work {
    # index.json is deliberately spared. It maps each input to the output it
    # produced, which is what makes re-running skip instead of rendering a
    # duplicate under a "(2)" name. Downloads also carry their date in the
    # filename, so losing the index costs less than it used to, but there is
    # no reason to throw it away with the scratch.
    if (-not (Test-Path "work")) { return @() }
    Get-ChildItem "work" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "index.json" }
}

Write-Host ""
Write-Host "  Tieulinh HOTA - clean up" -ForegroundColor Cyan
Write-Host "  Author: Nguyễn Thanh Hải" -ForegroundColor DarkGray
Line

$parts  = Measure-Set (Get-Parts)
$inputs = Measure-Set (Get-InputVideos)
$output = Measure-Set (Get-Output)
$work   = Measure-Set (Get-Work)

function Show-Drive {
    $root = [System.IO.Path]::GetPathRoot((Get-Location).Path)
    $d = Get-PSDrive -PSProvider FileSystem |
         Where-Object { $_.Root -eq $root } | Select-Object -First 1
    if (-not $d) { return }
    $total = $d.Used + $d.Free
    if ($total -le 0) { return }
    $pct = [int](100 * $d.Free / $total)
    $bar = "#" * [int]((100 - $pct) / 4) + "-" * [int]($pct / 4)
    Write-Host ""
    Write-Host ("  Drive {0}  [{1}]" -f $root, $bar)
    Write-Host ("    used {0}   free {1}   of {2}   ({3}% free)" -f `
        (GB $d.Used), (GB $d.Free), (GB $total), $pct) -ForegroundColor DarkGray
}

Show-Drive

Write-Host ""
Write-Host "  What this project is holding:"
Write-Host ""
Write-Host ("    1  unfinished downloads (.part)   {0,3} files  {1}" -f $parts.Count,  (GB $parts.Bytes))
Write-Host ("    2  input   source videos          {0,3} files  {1}" -f $inputs.Count, (GB $inputs.Bytes))
Write-Host ("    3  output  finished + chapters    {0,3} files  {1}" -f $output.Count, (GB $output.Bytes))
Write-Host ("    4  work    scratch + signal cache {0,3} files  {1}" -f $work.Count,   (GB $work.Bytes))
Write-Host ("    5  everything above                          {0}" -f (GB ($parts.Bytes + $inputs.Bytes + $output.Bytes + $work.Bytes)))
Write-Host "    0  cancel"

if ($parts.Count -gt 0) {
    Write-Host ""
    Write-Host "  Note: those .part files are unfinished downloads, not rubbish." -ForegroundColor Yellow
    Write-Host "        Start.cmd with the same link RESUMES from them." -ForegroundColor Yellow
    Write-Host "        Deleting them means downloading from zero again." -ForegroundColor Yellow
}
if ($output.Count -gt 0) {
    Write-Host ""
    Write-Host "  Note: output holds finished videos. Copy anything you want to" -ForegroundColor Yellow
    Write-Host "        keep before clearing it." -ForegroundColor Yellow
}

Write-Host ""
$choice = (Read-Host "  Choose").Trim()

$targets = switch ($choice) {
    "1" { @{ Name = "unfinished downloads"; Set = $parts } }
    "2" { @{ Name = "input videos";         Set = $inputs } }
    "3" { @{ Name = "output";               Set = $output } }
    "4" { @{ Name = "work";                 Set = $work } }
    "5" { @{ Name = "everything";
             Set = (Measure-Set (@(Get-Parts) + @(Get-InputVideos) + @(Get-Output) + @(Get-Work))) } }
    default { $null }
}

if (-not $targets) {
    Write-Host ""
    Write-Host "  Nothing deleted." -ForegroundColor Green
    Write-Host ""
    Read-Host "  Press Enter to close" | Out-Null
    exit 0
}
if ($targets.Set.Count -eq 0) {
    Write-Host ""
    Write-Host "  Nothing there to delete." -ForegroundColor Green
    Write-Host ""
    Read-Host "  Press Enter to close" | Out-Null
    exit 0
}

Line
Write-Host ""
Write-Host ("  About to send {0} file(s), {1}, to the Recycle Bin:" -f `
    $targets.Set.Count, (GB $targets.Set.Bytes))
Write-Host ""
$targets.Set.Files | Select-Object -First 12 | ForEach-Object {
    Write-Host ("    {0,8:N2} GiB  {1}" -f ($_.Length / 1GB), $_.Name)
}
if ($targets.Set.Count -gt 12) {
    Write-Host ("    ... and {0} more" -f ($targets.Set.Count - 12))
}

Write-Host ""
Write-Host "  They go to the Recycle Bin, so this can be undone." -ForegroundColor DarkGray
$confirm = (Read-Host "  Type DELETE to confirm").Trim()
if ($confirm -cne "DELETE") {
    Write-Host ""
    Write-Host "  Cancelled, nothing deleted." -ForegroundColor Green
    Write-Host ""
    Read-Host "  Press Enter to close" | Out-Null
    exit 0
}

$removed = 0
$freed = 0
foreach ($f in $targets.Set.Files) {
    try {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $f.FullName,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        $removed++
        $freed += $f.Length
    } catch {
        Write-Host ("  could not delete {0}: {1}" -f $f.Name, $_.Exception.Message) -ForegroundColor Red
    }
}

# Empty folders left behind under work\ are just noise.
if (Test-Path "work") {
    Get-ChildItem "work" -Directory -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Where-Object { -not (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue) } |
        ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

Line
Write-Host ""
Write-Host ("  Deleted {0} file(s), freed {1}." -f $removed, (GB $freed)) -ForegroundColor Green
Write-Host "  They are in the Recycle Bin if you need them back, which means the"
Write-Host "  space is not returned until you empty it." -ForegroundColor DarkGray
Show-Drive
Write-Host ""
Read-Host "  Press Enter to close" | Out-Null
