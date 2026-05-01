@echo off
cd /d "%~dp0"

"C:\Anaconda\envs\chatenv\python.exe" app.py

if errorlevel 1 (
  echo.
  echo 启动失败，请检查依赖或 Python 路径。
  pause
)