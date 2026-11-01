@echo off
rem Builds scheduler\visualisation\exports\scenario_viewer.html and opens it. Double-click this file.
rem It runs the script by its file path from the repository root, so it works from any terminal and
rem is not confused by another Python package that is also called "scheduler".
cd /d "%~dp0..\.."
where uv >nul 2>nul
if %errorlevel%==0 (
  uv run python scheduler\visualisation\scenario_viewer.py --html
) else (
  python scheduler\visualisation\scenario_viewer.py --html
)
if exist "scheduler\visualisation\exports\scenario_viewer.html" start "" "scheduler\visualisation\exports\scenario_viewer.html"
echo.
pause
