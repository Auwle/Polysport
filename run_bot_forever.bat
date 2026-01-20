@echo off
title LOL Trading Bot - Auto Restart
cd /d "%~dp0"

:loop
echo.
echo ========================================
echo Starting bot at %date% %time%
echo ========================================
echo.

python trading_bot.py

echo.
echo ========================================
echo Bot stopped at %date% %time%
echo Restarting in 10 seconds...
echo ========================================
timeout /t 10

goto loop
