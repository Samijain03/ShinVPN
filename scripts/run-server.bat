@echo off
title ShinVPN — Server Daemon
echo ========================================================
echo   SHINVPN SERVER DAEMON — DELUSIONAL CLUB INDUSTRIES
echo ========================================================
echo.
python -m shinvpn.cli.main server --config server.json
pause
