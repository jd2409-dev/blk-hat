@echo off
setlocal
set "ROOT=%~dp0"
call "%ROOT%blk-hat.cmd" %*
exit /b %errorlevel%
