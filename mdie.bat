@echo off
REM Launcher for the MDIE CLI.
REM Uses the project-local virtualenv when present, else the ambient python.
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -X utf8 -m cli %*
) else (
  python -X utf8 -m cli %*
)
