<#
    Set this project up on a fresh Windows 10 or 11 machine.

    No administrator rights are needed. Every dependency is a pip package, and
    ffmpeg travels inside imageio-ffmpeg, so nothing touches PATH, the registry
    or Program Files. Everything lands in a .venv folder beside this script.

    Python and deno are the two things pip cannot bring along. If either is
    missing this script installs it for you, per-user and quiet, so that
    stays admin-free too. deno is not optional for downloads: without it
    YouTube throttles them to about 1/50 speed. See tlh/jsruntime.py.

        Double-click Install.cmd

    Add -Force to rebuild the virtual environment from scratch.
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = "Stop"
# This script lives in scripts\, so the project root is one level up.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

function Say($text)  { Write-Host $text }
function Good($text) { Write-Host "  OK    $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  WARN  $text" -ForegroundColor Yellow }
function Bad($text)  { Write-Host "  FAIL  $text" -ForegroundColor Red }

Say ""
Say "tieu_linh_hota setup"
Say "Author: Nguyễn Thanh Hải"
Say "===================="

# ---------------------------------------------------------------- python ----
# Python is the one dependency pip cannot bring along, so if it is missing or
# too old this step installs it instead of giving up. Both routes are per-user
# installs, which is what keeps the whole setup free of admin rights: winget
# with --scope user first, then the python.org installer with InstallAllUsers=0.
Say ""
Say "[1/6] Python"
$minPython  = [version]"3.10"
$wantPython = "3.12"   # the version requirements.txt is verified against

function Get-PythonVersion($exe, $arg) {
    # Ask one candidate interpreter what version it is. Broken shims are
    # common here: a py.exe still pointing at an uninstalled Python311, or the
    # Microsoft Store python3 stub that only prints an advert. Keep their
    # noise off the screen and believe nothing that is not shaped like "3.12".
    $keep = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $code = "import sys;print('%d.%d'%sys.version_info[:2])"
        if ($arg) { $out = & $exe $arg -c $code 2>$null } else { $out = & $exe -c $code 2>$null }
        if ($LASTEXITCODE -ne 0) { return $null }
        foreach ($line in @($out)) {
            if ("$line".Trim() -match "^(\d+)\.(\d+)$") { return [version]$Matches[0] }
        }
    } catch { } finally { $ErrorActionPreference = $keep }
    return $null
}

function New-PythonCandidate($exe, $arg) {
    $label = if ($arg) { "$exe $arg" } else { $exe }
    [pscustomobject]@{ Exe = $exe; Arg = $arg; Label = $label }
}

function Get-PythonCandidates {
    $list = @()
    # The launcher knows every registered install and hands back the newest,
    # so it is asked first.
    if (Get-Command py -ErrorAction SilentlyContinue) { $list += New-PythonCandidate "py" "-3" }
    # Then interpreters sitting in the standard install folders, newest first:
    # a fresh 3.12 under LOCALAPPDATA has to beat an old 3.9 that happens to
    # own the name `python` on PATH.
    $globs = @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
               "$env:ProgramFiles\Python3*\python.exe",
               "${env:ProgramFiles(x86)}\Python3*\python.exe",
               "$env:SystemDrive\Python3*\python.exe")
    $found = @(Get-ChildItem -Path $globs -ErrorAction SilentlyContinue |
               Sort-Object { [int]($_.Directory.Name -replace "\D", "") } -Descending)
    foreach ($item in $found) { $list += New-PythonCandidate $item.FullName $null }
    # Finally whatever PATH offers, minus the WindowsApps aliases, which are
    # not interpreters at all.
    foreach ($name in @("python", "python3")) {
        foreach ($cmd in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($cmd.Source -and $cmd.Source -notlike "*\WindowsApps\*") {
                $list += New-PythonCandidate $cmd.Source $null
            }
        }
    }
    $seen = @{}
    $list | Where-Object { if ($seen[$_.Label]) { $false } else { $seen[$_.Label] = $true; $true } }
}

function Find-Python {
    $tooOld = $null
    foreach ($candidate in @(Get-PythonCandidates)) {
        $version = Get-PythonVersion $candidate.Exe $candidate.Arg
        if (-not $version) { continue }
        if ($version -ge $minPython) {
            Good "found Python $version via '$($candidate.Label)'"
            return $candidate
        }
        if (-not $tooOld -or $version -gt $tooOld) { $tooOld = $version }
    }
    if ($tooOld) { Warn "the newest Python here is $tooOld; $minPython or newer is needed" }
    return $null
}

function Update-EnvPath {
    # An install writes PATH into the registry, but this process is still
    # holding the copy it started with, so read it back rather than telling
    # the user to close the window and start again.
    $parts = @([Environment]::GetEnvironmentVariable("PATH", "Machine"),
               [Environment]::GetEnvironmentVariable("PATH", "User")) |
             Where-Object { $_ }
    if ($parts) { $env:PATH = $parts -join ";" }
}

function Install-PythonWithWinget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
    Say "  trying winget install Python.Python.$wantPython --scope user"
    # Out-Host, not the output stream: winget is chatty and its chatter must
    # not end up as this function's return value.
    & winget install --id "Python.Python.$wantPython" --exact --source winget `
        --scope user --silent --disable-interactivity `
        --accept-package-agreements --accept-source-agreements | Out-Host
    if ($LASTEXITCODE -eq 0) { return $true }
    # Not every Python manifest ships a per-user installer, and a machine-wide
    # one would ask for admin, so fall through to python.org instead.
    Warn "winget did not install it (exit $LASTEXITCODE)"
    return $false
}

function Install-PythonFromPythonOrg {
    $suffix = switch ($env:PROCESSOR_ARCHITECTURE) {
        "AMD64" { "-amd64" }
        "ARM64" { "-arm64" }
        default { "" }        # the 32-bit x86 installer carries no suffix
    }
    # PowerShell 5.1 still defaults to TLS 1.0, which python.org refuses.
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch { }
    Say "  asking python.org for the newest $wantPython release"
    try {
        $index = Invoke-WebRequest "https://www.python.org/ftp/python/" -UseBasicParsing -TimeoutSec 60
    } catch {
        Bad "cannot reach python.org: $($_.Exception.Message)"
        return $false
    }
    $pattern = 'href="(' + [regex]::Escape($wantPython) + '\.\d+)/"'
    $versions = @([regex]::Matches($index.Content, $pattern) |
                  ForEach-Object { $_.Groups[1].Value } |
                  Sort-Object { [version]$_ } -Descending)
    foreach ($version in $versions) {
        $url = "https://www.python.org/ftp/python/$version/python-$version$suffix.exe"
        # Security-only releases are source code with no installer, so check
        # that this one exists before committing to a 25 MB download.
        try { $null = Invoke-WebRequest $url -Method Head -UseBasicParsing -TimeoutSec 60 } catch { continue }
        $file = Join-Path $env:TEMP "python-$version$suffix.exe"
        Say "  downloading $url"
        try {
            Invoke-WebRequest $url -OutFile $file -UseBasicParsing -TimeoutSec 900
        } catch {
            Bad "download failed: $($_.Exception.Message)"
            return $false
        }
        Say "  installing quietly; this takes a minute"
        # InstallAllUsers=0 with InstallLauncherAllUsers=0 keeps everything
        # inside the user profile, and that is what avoids the admin prompt.
        $run = Start-Process -FilePath $file -Wait -PassThru -ArgumentList @(
            "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1",
            "InstallLauncherAllUsers=0", "Include_test=0", "Include_doc=0",
            "AssociateFiles=0", "Shortcuts=0")
        Remove-Item $file -ErrorAction SilentlyContinue
        if ($run.ExitCode -eq 0 -or $run.ExitCode -eq 3010) { return $true }
        Bad "the Python installer failed (exit $($run.ExitCode))"
        return $false
    }
    Bad "python.org lists no $wantPython installer for this machine"
    return $false
}

$python = Find-Python
if (-not $python) {
    Say ""
    Say "  installing Python $wantPython for you (per-user, no admin needed)"
    if (Install-PythonWithWinget) { Update-EnvPath; $python = Find-Python }
    if (-not $python -and (Install-PythonFromPythonOrg)) { Update-EnvPath; $python = Find-Python }
}
if (-not $python) {
    Bad "no Python 3.10+ found, and installing it automatically did not work."
    Say ""
    Say "  Install it by hand WITHOUT admin rights, either way:"
    Say "    winget install Python.Python.3.12 --scope user"
    Say "  or python.org, ticking 'Install for me only' (not 'for all users')."
    Say "  Then run this script again."
    exit 1
}

# ------------------------------------------------------------------ deno ----
# yt-dlp has to run YouTube's own JavaScript to solve the `n` parameter of a
# stream URL. Without a runtime the download still succeeds and is about fifty
# times slower -- 10 MiB, then a minute of nothing, over and over -- and
# nothing on screen says why. deno is the one to install: yt-dlp enables only
# deno by default and vendors a solver script for it, while node is rejected
# below v22. tlh/jsruntime.py has the measurements and finds it again later.
Say ""
Say "[2/6] helper tools (deno, aria2c)"
$minDeno = [version]"2.3.0"
$denoDir = Join-Path $root ".tools"
$denoExe = Join-Path $denoDir "deno.exe"

function Get-DenoVersion($exe) {
    $keep = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe --version 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        foreach ($line in @($out)) {
            if ("$line" -match "deno\s+(\d+\.\d+\.\d+)") { return [version]$Matches[1] }
        }
    } catch { } finally { $ErrorActionPreference = $keep }
    return $null
}

function Find-Deno {
    # Same order as tlh/jsruntime.py: our own copy, then the official install
    # location, then PATH.
    $paths = @($denoExe, (Join-Path $env:USERPROFILE ".deno\bin\deno.exe"))
    $onPath = Get-Command deno -ErrorAction SilentlyContinue
    if ($onPath -and $onPath.Source) { $paths += $onPath.Source }
    foreach ($path in $paths) {
        if (-not (Test-Path $path)) { continue }
        $version = Get-DenoVersion $path
        if ($version -and $version -ge $minDeno) {
            return [pscustomobject]@{ Path = $path; Version = $version }
        }
    }
    return $null
}

function Install-DenoWithWinget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
    Say "  trying winget install DenoLand.Deno"
    # The package is a portable zip, so winget puts it under the user profile
    # and needs no --scope of its own.
    & winget install --id DenoLand.Deno --exact --source winget --silent `
        --disable-interactivity --accept-package-agreements --accept-source-agreements | Out-Host
    if ($LASTEXITCODE -eq 0) { return $true }
    Warn "winget did not install deno (exit $LASTEXITCODE)"
    return $false
}

function Install-DenoFromGitHub {
    # The release is a zip holding one exe, so there is nothing to install:
    # unpack it into .tools\ and let tlh/jsruntime.py look there first. No
    # PATH entry, no registry, nothing to uninstall.
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "aarch64" } else { "x86_64" }
    $url = "https://github.com/denoland/deno/releases/latest/download/deno-$arch-pc-windows-msvc.zip"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch { }
    $zip = Join-Path $env:TEMP "deno-$arch.zip"
    $tmp = Join-Path $env:TEMP ("deno-unpack-" + [guid]::NewGuid().ToString("N"))
    Say "  downloading $url"
    try {
        Invoke-WebRequest $url -OutFile $zip -UseBasicParsing -TimeoutSec 600
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    } catch {
        Bad "could not fetch deno: $($_.Exception.Message)"
        Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
        return $false
    }
    $exe = Get-ChildItem -Path $tmp -Filter deno.exe -Recurse -ErrorAction SilentlyContinue |
           Select-Object -First 1
    if (-not $exe) {
        Bad "the deno zip held no deno.exe"
        Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
        return $false
    }
    if (-not (Test-Path $denoDir)) { New-Item -ItemType Directory $denoDir | Out-Null }
    Move-Item $exe.FullName $denoExe -Force
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    return $true
}

$deno = Find-Deno
if (-not $deno) {
    Say "  none found; installing deno (per-user, no admin needed)"
    if (Install-DenoWithWinget) { Update-EnvPath; $deno = Find-Deno }
    if (-not $deno -and (Install-DenoFromGitHub)) { $deno = Find-Deno }
}
if ($deno) {
    Good "deno $($deno.Version) at $($deno.Path)"
} else {
    # Not fatal: cutting files already in input\ needs none of this.
    Warn "no deno. Cutting local files still works, but a --url download would"
    Warn "crawl at roughly 1/50 speed. Install it by hand with:"
    Say  "    winget install DenoLand.Deno --scope user"
}

# googlevideo caps ONE connection at about 1 MiB/s, so a download has to hold
# several. yt-dlp does that by opening a new connection for every 10 MiB
# fragment -- 600 of them for one VOD -- and a home line stops answering new
# ones after a quarter of an hour of it. aria2c opens eight and keeps them.
# tlh/aria2.py has the measurements; without it the pipeline still works, on
# yt-dlp's fragments.
function Find-Aria2 {
    $paths = @((Join-Path $root ".tools\aria2c.exe"),
               (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\aria2c.exe"))
    # The portable package unpacks into a version-stamped folder of its own,
    # so this has to look deeper than one level.
    $paths += @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") `
                    -Filter aria2c.exe -Recurse -ErrorAction SilentlyContinue |
                ForEach-Object { $_.FullName })
    $onPath = Get-Command aria2c -ErrorAction SilentlyContinue
    if ($onPath -and $onPath.Source) { $paths += $onPath.Source }
    foreach ($path in $paths) {
        if (-not (Test-Path $path)) { continue }
        $keep = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $out = & $path --version 2>$null
            foreach ($line in @($out)) {
                if ("$line" -match "aria2 version (\S+)") {
                    return [pscustomobject]@{ Path = $path; Version = $Matches[1] }
                }
            }
        } catch { } finally { $ErrorActionPreference = $keep }
    }
    return $null
}

$aria2 = Find-Aria2
if (-not $aria2) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say "  trying winget install aria2.aria2"
        # Portable zip, so it lands under the user profile with no --scope.
        & winget install --id aria2.aria2 --exact --source winget --silent `
            --disable-interactivity --accept-package-agreements --accept-source-agreements | Out-Host
        if ($LASTEXITCODE -eq 0) { Update-EnvPath; $aria2 = Find-Aria2 }
    }
}
if ($aria2) {
    Good "aria2c $($aria2.Version) at $($aria2.Path)"
} else {
    # Not fatal, and not even needed for local files: downloads simply fall
    # back to yt-dlp's own fragment pool, which works and churns connections.
    Warn "no aria2c. Downloads will use yt-dlp's fragments instead, which is"
    Warn "slower on a home line. Install it by hand with:"
    Say  "    winget install aria2.aria2"
}

# ------------------------------------------------------------------ venv ----
Say ""
Say "[3/6] virtual environment"
$venv = Join-Path $root ".venv"
if ($Force -and (Test-Path $venv)) {
    Say "  removing the old .venv (-Force)"
    Remove-Item -Recurse -Force $venv
}
if (-not (Test-Path $venv)) {
    if ($python.Arg) { & $python.Exe $python.Arg -m venv $venv } else { & $python.Exe -m venv $venv }
    if (-not $?) { Bad "could not create the virtual environment"; exit 1 }
    Good "created .venv"
} else {
    Good ".venv already present (use -Force to rebuild)"
}
$venvPython = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Bad "no python.exe inside .venv"; exit 1 }

# ------------------------------------------------------------ dependencies --
Say ""
Say "[4/6] dependencies"
& $venvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPython -m pip install -r (Join-Path $root "requirements.txt") --quiet --disable-pip-version-check
if (-not $?) { Bad "pip install failed"; exit 1 }
Good "installed from requirements.txt"

# ---------------------------------------------------------------- folders ---
Say ""
Say "[5/6] folders"
foreach ($dir in @("input", "output", "work")) {
    $path = Join-Path $root $dir
    if (-not (Test-Path $path)) { New-Item -ItemType Directory $path | Out-Null }
    Good "$dir/"
}

# -------------------------------------------------------------- self test ---
Say ""
Say "[6/6] self test"
$check = @'
import sys
sys.path.insert(0, ".")
import numpy, cv2, imageio_ffmpeg
print("  OK    numpy", numpy.__version__)
print("  OK    opencv", cv2.__version__)
print("  OK    ffmpeg", imageio_ffmpeg.get_ffmpeg_version())
try:
    import yt_dlp
    print("  OK    yt-dlp", yt_dlp.version.__version__)
    # yt-dlp fetches video and audio separately and needs ffmpeg to mux them,
    # but it only looks on PATH. Check now: otherwise the failure arrives after
    # a 2.6 GB download has already finished.
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
    from tlh.ffmpeg import FF
    pp = FFmpegPostProcessor(yt_dlp.YoutubeDL(
        {"quiet": True, "no_warnings": True, "ffmpeg_location": FF}))
    if pp.available:
        print("  OK    yt-dlp can reach ffmpeg for merging")
    else:
        print("  FAIL  yt-dlp cannot reach ffmpeg; downloads would abort after"
              " finishing")
        sys.exit(1)
except ImportError:
    print("  WARN  yt-dlp missing: --url downloads will not work")
# Check the JS runtime from the same code the downloader uses, so this cannot
# pass while the download path disagrees. Discovering it is missing here is
# the whole point: the alternative is finding out ten hours into a download
# that should have taken ten minutes.
from tlh import jsruntime
deno, deno_version = jsruntime.describe()
if deno:
    print(f"  OK    deno {deno_version} for YouTube's n-parameter")
else:
    print("  WARN  no deno: --url downloads would run at about 1/50 speed.")
    print("       ", jsruntime.WHY)
    print("        fix:", jsruntime.INSTALL_HINT)
from tlh import aria2, fetch
fast, fast_version = aria2.describe()
if fast:
    print(f"  OK    aria2c {fast_version}, {fetch.ARIA2_CONNECTIONS} connections")
else:
    print("  WARN  no aria2c: downloads fall back to yt-dlp's fragments.")
    print("       ", aria2.WHY)
    print("        fix:", aria2.INSTALL_HINT)
from tlh import encoder, config
missing = [n for n in ("tieulinh_name", "lobby_header", "lobby_buttons",
                       "menu_options", "menu_logo", "reconnect_abort",
                       "spell_left", "spell_right")
           if not (config.TEMPLATES / (n + ".png")).exists()]
if missing:
    print("  FAIL  templates/ is missing:", ", ".join(missing))
    sys.exit(1)
if not (config.TEMPLATES / "digits.npz").exists():
    print("  FAIL  templates/digits.npz is missing")
    sys.exit(1)
print("  OK    templates present")
name, flag = encoder.detect(log=lambda *a: None, force=True)
print("  OK    video encoder:", name)
if name == "libx264":
    print("  WARN  no hardware encoder on this machine; rendering will be"
          " roughly 3x slower")
'@
$checkFile = Join-Path $env:TEMP "tlh_selftest.py"
Set-Content -Path $checkFile -Value $check -Encoding utf8
& $venvPython $checkFile
$ok = $?
Remove-Item $checkFile -ErrorAction SilentlyContinue
if (-not $ok) { Bad "self test failed"; exit 1 }

Say ""
Say "Ready."
Say ""
Say "  Double-click Start.cmd, paste a YouTube link, and wait."
Say "  Or drop videos into input\ and run:  .venv\Scripts\python.exe run.py"
Say ""
