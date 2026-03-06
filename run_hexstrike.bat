@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "CLI=%SCRIPT_DIR%ollama_hexstrike_cli.py"

if not exist "%CLI%" (
  echo ERROR: Cannot find ollama_hexstrike_cli.py in %SCRIPT_DIR%
  exit /b 1
)

python "%CLI%" --auto-start-hexstrike --install-hexstrike-deps %*
exit /b %errorlevel%
