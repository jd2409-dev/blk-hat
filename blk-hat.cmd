@echo off
setlocal

set "ROOT=%~dp0"
set "APP=%ROOT%blk_hat_app.py"
set "VENV=%ROOT%hexstrike_env\Scripts\python.exe"

if not exist "%APP%" (
  echo ERROR: Cannot find blk_hat_app.py in %ROOT%
  exit /b 1
)

if not exist "%VENV%" (
  echo ERROR: Cannot find virtual environment at %VENV%
  exit /b 1
)

"%VENV%" "%APP%" repl %*
exit /b %errorlevel%
