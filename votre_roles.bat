@echo off
set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%docs\team_structure.html" (
  echo Error: docs\team_structure.html not found in %SCRIPT_DIR%
  exit /b 1
)
if not exist "%SCRIPT_DIR%docs\branch_responsibilities.html" (
  echo Error: docs\branch_responsibilities.html not found in %SCRIPT_DIR%
  exit /b 1
)
start "" "%SCRIPT_DIR%docs\team_structure.html"
start "" "%SCRIPT_DIR%docs\branch_responsibilities.html"
