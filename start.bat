@echo off
title SpotiFetch Server
echo ========================================================
echo   Starting SpotiFetch - Spotify Media Downloader Server
echo ========================================================
echo.
echo Opening browser at http://localhost:8000 ...
start http://localhost:8000
echo.
python main.py
pause
