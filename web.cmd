@echo off
rem Switch the console to UTF-8 first. Windows 11 usually copes, but a
rem Windows 10 console is often codepage 437 or 1252, which renders the
rem Vietnamese text in the banners as rubbish.
chcp 65001 >nul
rem Double-click this to open the web page: paste a link, watch where each job
rem is, run a file from input\ again. Leave this window open -- the jobs run
rem underneath it, and closing it stops them.
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m tlh.web --open
) else (
    echo   No .venv found. Double-click Install.cmd first.
    pause
    exit /b 1
)
rem Pause only if it fell over: a normal Ctrl+C exit needs no keypress.
if errorlevel 1 pause
