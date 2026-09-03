@echo off
setlocal EnableExtensions

REM =====================================================================
REM  THE LEDGER - IFSCA / SEBI exam preparation launcher
REM
REM  Usage:   start.bat [port] [dev]     (the two may be given in either order)
REM             start.bat              127.0.0.1:8000, no hot reload
REM             start.bat 8020         127.0.0.1:8020
REM             start.bat 8020 dev     127.0.0.1:8020 with uvicorn --reload
REM             start.bat dev 8020     same as above
REM             start.bat dev          default port, with --reload
REM           The port may also come from a PORT environment variable.
REM
REM  The server runs in its own window so that this launcher can wait for
REM  /health to answer before opening the browser. Close that window, or
REM  press Ctrl+C in it, to stop the app.
REM =====================================================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "DB_FILE=%BACKEND_DIR%\ifsca_exam.db"

REM Every external tool below is called by absolute System32 path, never by PATH
REM lookup. A Git Bash prompt puts MSYS bin first on PATH, where GNU coreutils
REM ships its own timeout.exe; that shadow made the readiness loop burn all its
REM attempts in seconds and report a startup failure while the server was in
REM fact healthy. System32 has no spaces, so these stay unquoted for /f safety.
if not defined SystemRoot set "SystemRoot=C:\Windows"
set "SYS32=%SystemRoot%\System32"

REM --- arguments -------------------------------------------------------
REM Port and "dev" are accepted in either order; without the second else-branch
REM `start.bat dev 8020` would silently serve 8000 and ignore the explicit port.
if /I "%~1"=="dev" (set "RELOAD_FLAG=--reload") else (if not "%~1"=="" set "PORT=%~1")
if /I "%~2"=="dev" (set "RELOAD_FLAG=--reload") else (if not "%~2"=="" set "PORT=%~2")
if "%PORT%"=="" set "PORT=8000"

cd /d "%PROJECT_ROOT%"

echo.
echo =====================================================================
echo  THE LEDGER - startup
echo =====================================================================
echo   Tree         : %PROJECT_ROOT%
if not "%PROJECT_ROOT:.worktrees=%"=="%PROJECT_ROOT%" echo   NOTE         : this is a git WORKTREE, not the main checkout.
echo   Backend      : %BACKEND_DIR%
if exist "%DB_FILE%" (
    for %%F in ("%DB_FILE%") do echo   Database     : %DB_FILE%  [%%~zF bytes]
) else (
    echo   Database     : %DB_FILE%  [absent - created and seeded on first boot]
)
echo   URL          : http://127.0.0.1:%PORT%
if defined RELOAD_FLAG (echo   Hot reload   : ON  [dev flag - restarts the scheduler on every edit]) else (echo   Hot reload   : off [pass "dev" to enable])
echo.

REM DB_PATH is tree-relative, so launching the wrong checkout silently reads
REM and writes a different database. The lines above exist to make that visible.

REM --- interpreter -----------------------------------------------------
%SYS32%\where.exe python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH. Install Python 3.10 or newer.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('python -c "import sys;print(sys.version.split()[0], sys.executable)"') do echo   Interpreter  : %%V
echo.

REM --- dependencies ----------------------------------------------------
REM Probe the real entrypoint rather than a folder or a hand-kept module list.
REM "import main" pulls in every module the app loads at startup, so it cannot
REM drift when a dependency is added, and its traceback names what is missing.
echo Checking dependencies by importing the application...
cd /d "%BACKEND_DIR%"
python -c "import main" >nul 2>&1
if errorlevel 1 goto DEPS_MISSING
echo   OK - application imports cleanly.
echo.
goto PORT_CHECK

:DEPS_MISSING
echo.
echo   FAILED - the application could not be imported. The real error:
echo   -----------------------------------------------------------------
python -c "import main"
echo   -----------------------------------------------------------------
echo.
echo This interpreter is missing packages. Two ways forward:
echo   1. Install them for the interpreter above:
echo        python -m pip install -r "%BACKEND_DIR%\requirements.txt"
echo   2. Let this script create a venv in the tree and install into it.
echo.
set /p MAKE_VENV="Create %PROJECT_ROOT%\venv and install requirements.txt now? [Y/N] "
if /I not "%MAKE_VENV%"=="Y" (
    echo Not creating a venv. Nothing was started.
    pause
    exit /b 1
)
echo.
echo Creating venv...
python -m venv "%PROJECT_ROOT%\venv"
if errorlevel 1 (
    echo ERROR: venv creation failed.
    pause
    exit /b 1
)
call "%PROJECT_ROOT%\venv\Scripts\activate.bat"
echo Installing dependencies - PyMuPDF and google-genai are large, this takes a while...
python -m pip install --upgrade pip >nul
python -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: dependency install failed.
    pause
    exit /b 1
)
python -c "import main" >nul 2>&1
if errorlevel 1 (
    echo ERROR: still cannot import the application after installing into the venv.
    pause
    exit /b 1
)
echo   OK - application imports cleanly inside the venv.
echo.

REM --- port collision --------------------------------------------------
:PORT_CHECK
REM Probe the exact binary the readiness loop will call, not "a curl on PATH":
REM PATH could resolve to some other curl while this one is missing.
if not exist "%SYS32%\curl.exe" (
    echo ERROR: %SYS32%\curl.exe was not found. It ships with Windows 10 1803 and
    echo later, and this script uses it to poll /health before opening the browser.
    echo.
    pause
    exit /b 1
)

set "CONN_PID="
for /f "tokens=5" %%p in ('%SYS32%\netstat.exe -ano -p tcp ^| %SYS32%\findstr.exe /R /C:":%PORT% .*LISTENING"') do set "CONN_PID=%%p"
if defined CONN_PID (
    echo ERROR: port %PORT% is already listening - owning PID %CONN_PID%.
    echo Something is already serving on http://127.0.0.1:%PORT%, possibly the
    echo OTHER checkout of this project. Refusing to start a second tree on the
    echo same URL, because the browser would not show you the code you launched.
    echo.
    echo To identify it:   tasklist /FI "PID eq %CONN_PID%"
    echo To stop it:       taskkill /PID %CONN_PID%
    echo Or pick another:  start.bat 8020
    echo.
    pause
    exit /b 1
)

REM --- launch ----------------------------------------------------------
REM Keys are NOT checked by testing for backend\.env. They are published as
REM user-level environment variables - see
REM docs\adr\0003-gemini-keys-as-user-environment-variables.md - so a tree with
REM no .env is normal. /health reports the count that actually resolved.
echo Starting uvicorn on 127.0.0.1:%PORT% in a separate window...
start "LEDGER SERVER :%PORT%" cmd /k python -m uvicorn main:app --host 127.0.0.1 --port %PORT% %RELOAD_FLAG%

REM --- readiness gate --------------------------------------------------
REM The browser opens only after /health answers, so the first load is never a
REM connection-refused page. Bounded at 90 attempts; each costs a ~1s sleep plus
REM up to 2s of curl timeout, so the ceiling is minutes, not 90 seconds.
set "HEALTH_FILE=%TEMP%\ledger_health_%PORT%.json"
set "CODE_FILE=%TEMP%\ledger_health_%PORT%.code"
set /a TRIES=0
echo Waiting for /health...

:WAIT_READY
%SYS32%\curl.exe -s -m 2 -o "%HEALTH_FILE%" -w "%%{http_code}" "http://127.0.0.1:%PORT%/health" > "%CODE_FILE%" 2>nul
set "HTTP_CODE="
set /p HTTP_CODE=<"%CODE_FILE%"
if "%HTTP_CODE%"=="200" goto READY
set /a TRIES+=1
if %TRIES% GEQ 90 goto STARTUP_FAILED
REM ping, not "timeout /t": timeout.exe refuses to run when stdin is not a
REM console, and GNU coreutils shadows it on a Git Bash PATH.
%SYS32%\ping.exe -n 2 127.0.0.1 >nul
goto WAIT_READY

:READY
echo   READY after %TRIES% attempt(s) - /health answered 200.
echo.
python -c "import json,sys;d=json.load(open(r'%HEALTH_FILE%',encoding='utf-8'));print('   Gemini keys      :',d.get('api_keys_loaded'));print('   gemini_available :',d.get('gemini_available'));print('   central AI ready :',d.get('central_ai_ready'));print('   database ready   :',d.get('database_initialized'));sys.exit(0 if d.get('api_keys_loaded') else 1)"
if errorlevel 1 (
    echo.
    echo WARNING: no Gemini keys were confirmed, or /health could not be read.
    echo Gemini is mandatory here - these will fail without keys:
    echo   POST /api/exams/start and every phase paper
    echo   smart mock generation
    echo   essay, precis and reading-comprehension grading
    echo Keys are user-level environment variables GEMINI_KEY_1..9 - see ADR-0003.
    echo A shell opened before they were published will not see them: open a new
    echo one, or launch this script from Explorer.
    echo.
)

start "" "http://127.0.0.1:%PORT%"
echo Opening http://127.0.0.1:%PORT% in your browser.
echo.
echo The server keeps running in the "LEDGER SERVER :%PORT%" window.
echo Stop it there with Ctrl+C, or close that window.
echo.
del "%HEALTH_FILE%" "%CODE_FILE%" >nul 2>&1
endlocal
exit /b 0

:STARTUP_FAILED
echo.
echo ERROR: /health did not answer 200 after 90 attempts.
echo The server window may still be open with the real traceback - read it there.
echo Nothing was opened in the browser.
echo.
del "%HEALTH_FILE%" "%CODE_FILE%" >nul 2>&1
pause
endlocal
exit /b 1
