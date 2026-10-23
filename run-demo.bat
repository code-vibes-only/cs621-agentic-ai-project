@echo off
rem Start the demo app on Windows: double-click this file. It opens on http://localhost:8501.
rem There is no separate backend: the agents, the coordinator and the demo's SQLite store
rem (data\demo\app.db) all run inside this one Streamlit process. Stop it with Ctrl+C.
setlocal
cd /d "%~dp0"
rem The port the app opens on: change it here if 8501 is taken.
set "PORT=8501"
set "PYTHONUTF8=1"

rem Find uv: on PATH, where its installer puts it, or in a user Python's Scripts folder (pip install --user uv).
set "UV="
for /f "delims=" %%i in ('where uv 2^>nul') do if not defined UV set "UV=%%i"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV for /d %%d in ("%APPDATA%\Python\Python3*") do if exist "%%d\Scripts\uv.exe" set "UV=%%d\Scripts\uv.exe"
if not defined UV (
    echo Could not find uv. Install it, then run this again:
    echo     py -m pip install --user uv
    echo or see https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

echo Installing or updating the demo packages...
"%UV%" sync --group demo
if errorlevel 1 (
    echo uv sync failed: see the message above.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo No .env file: only "Mocked LLM only" works, at no cost. For the real model, copy .env.example
    echo to .env and put your own OPENAI_API_KEY in it. Never commit .env.
)

echo.
echo Starting the demo on http://localhost:%PORT%  (Ctrl+C to stop)
echo Sign in as alice, bob, charlie, damian, eve, felicia, george, hannah, ignatius or jack;
echo each password is the username.
echo.
rem Only this computer can reach it (the demo passwords are the usernames), and Streamlit's usage statistics are off.
"%UV%" run --group demo python -m streamlit run scheduler/demo/app.py --server.port %PORT% --server.address localhost --browser.gatherUsageStats false
pause
