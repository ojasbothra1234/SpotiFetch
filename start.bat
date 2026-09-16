@echo off
title SpotiFetch Server
echo ========================================================
echo   Starting SpotiFetch - Spotify Media Downloader Server
echo ========================================================
echo.
echo Opening browser at http://localhost:5000 ...
start http://localhost:5000
echo.
python main.py --port 5000

pause
