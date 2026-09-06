@echo off
rem Switch the console to UTF-8 first. Windows 11 usually copes, but a
rem Windows 10 console is often codepage 437 or 1252, which renders the
rem Vietnamese text in the banners as rubbish.
chcp 65001 >nul
rem Double-click this ONCE to install. Windows opens .ps1 files in Notepad, so
rem the clickable file has to be a .cmd; it just calls the real script.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
pause
