@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERRO: ambiente Python x86 nao encontrado em .venv.
  pause
  exit /b 2
)

".venv\Scripts\python.exe" "scripts\probe_discovered_databases.py" --pausar
exit /b %ERRORLEVEL%
