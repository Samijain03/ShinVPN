@echo off
title ShinVPN — Client Terminal
echo ========================================================
echo   SHINVPN CLIENT TERMINAL — DELUSIONAL CLUB INDUSTRIES
echo ========================================================
echo.
python -m shinvpn.cli.main client --config client.json
pause
