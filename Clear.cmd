@echo off
rem Switch the console to UTF-8 first. Windows 11 usually copes, but a
rem Windows 10 console is often codepage 437 or 1252, which renders the
rem Vietnamese text in the banners as rubbish.
chcp 65001 >nul
rem Double-click to free up disk space. It shows what it will remove and asks
rem twice; everything goes to the Recycle Bin, so a misclick is recoverable.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\clear.ps1" %*
