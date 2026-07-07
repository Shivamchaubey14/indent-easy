@echo off
REM Save this as start_services.bat in your project root

SETLOCAL ENABLEDELAYEDEXPANSION

REM Define absolute paths
SET PROJECT_ROOT=C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project
SET PIPFILE=%PROJECT_ROOT%\Pipfile
SET MANAGE_PY=%PROJECT_ROOT%\manage.py

REM Force Pipenv to use the correct Pipfile
SET PIPENV_PIPFILE=%PIPFILE%

cls
echo ==========================================
echo    SHWETDHARA EASY INDENT SYSTEM
echo ==========================================
echo Project Root: %PROJECT_ROOT%
echo Pipfile: %PIPFILE%
echo ==========================================
echo.

REM Verify files exist
IF NOT EXIST "%MANAGE_PY%" (
    echo ERROR: manage.py not found at %MANAGE_PY%
    pause
    exit /b 1
)

IF NOT EXIST "%PIPFILE%" (
    echo ERROR: Pipfile not found at %PIPFILE%
    pause
    exit /b 1
)

REM Start Windows Terminal with all services
echo Starting all services in Windows Terminal...
echo.

REM The key fix: using --startingDirectory for EACH tab and proper PowerShell escaping
wt.exe --window maxwidth 100 maxheight 30 ^
    --startingDirectory "%PROJECT_ROOT%" --title "Django Server" powershell -NoExit -Command "pipenv run python manage.py runserver" ^
    nt --startingDirectory "%PROJECT_ROOT%" --title "Celery Beat" powershell -NoExit -Command "pipenv run celery -A shwetDhara_project beat --loglevel=info" ^
    nt --startingDirectory "%PROJECT_ROOT%" --title "MQ Worker" powershell -NoExit -Command "pipenv run celery -A shwetDhara_project worker -Q message_queue --loglevel=info --hostname=message@%%h" ^
    nt --startingDirectory "%PROJECT_ROOT%" --title "General Worker" powershell -NoExit -Command "pipenv run celery -A shwetDhara_project worker -Q default --loglevel=info --hostname=general@%%h"

echo.
echo ==========================================
echo ALL SERVICES STARTED SUCCESSFULLY
echo ==========================================
echo.
echo http://127.0.0.1:8000
echo.
pause