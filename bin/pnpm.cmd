@echo off
set "PATH=%~dp0..\.runtime\node-v24.18.0-win-x64;%PATH%"
set "COREPACK_HOME=%~dp0..\.runtime\corepack"
"%~dp0..\.runtime\node-v24.18.0-win-x64\pnpm.cmd" %*

