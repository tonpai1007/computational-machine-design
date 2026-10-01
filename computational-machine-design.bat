@echo off
REM Launcher for the computational-machine-design CLI.
REM Uses the project-local virtualenv when present, else the ambient python.
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m cli %*
) else (
  python -m cli %*
)
