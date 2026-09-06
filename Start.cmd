@echo off
rem Switch the console to UTF-8 first. Windows 11 usually copes, but a
rem Windows 10 console is often codepage 437 or 1252, which renders the
rem Vietnamese text in the banners as rubbish.
chcp 65001 >nul
rem Double-click this to download a stream and cut it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\download_and_cut.ps1" %*
rem Pause only if PowerShell itself fell over before its own prompt: every
rem normal exit already waits for Enter inside the script.
if errorlevel 1 pause
