@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not defined ANTHROPIC_BASE_URL set "ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic"
if not defined ANTHROPIC_MODEL set "ANTHROPIC_MODEL=MiniMax-M2.7"
if exist "%~dp0astrid\main.py" (
  cd /d "%~dp0"
  python -m astrid.main %*
) else (
  astrid %*
)
