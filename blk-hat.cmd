@echo off
setlocal

set "ROOT=%~dp0"
set "APP=%ROOT%blk_hat_app.py"

if not exist "%APP%" (
  echo ERROR: Cannot find blk_hat_app.py in %ROOT%
  exit /b 1
)

py -3 -c "import typer, requests" >nul 2>&1
if errorlevel 1 (
  py -3 -m pip install --user --upgrade typer requests >nul
  if errorlevel 1 exit /b 1
)

py -3 "%APP%" repl %*
exit /b %errorlevel%
