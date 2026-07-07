# ==========================================================
# SHWETDHARA EASY INDENT SYSTEM LAUNCHER
# UPDATED FOR WHATSAPP BUSINESS API TEMPLATE SYSTEM
# NO WHATSAPP DESKTOP REQUIRED - USES META BUSINESS API
# WHATSAPP API SERVICE IS NOW MONITOR ONLY
# ==========================================================

$ProjectRoot  = "D:\shwetDhara_Project_v4\shwetDhara_project"
$PipfilePath  = "$ProjectRoot\Pipfile"
$RedisExePath = "C:\Program Files\Redis\redis-server.exe"

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   SHWETDHARA EASY INDENT SYSTEM" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Project Root : $ProjectRoot" -ForegroundColor Green
Write-Host "Pipfile Path : $PipfilePath" -ForegroundColor Green
Write-Host "WhatsApp Mode: MONITOR ONLY (Celery sends messages)" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------
# BASIC VALIDATION
# ----------------------------------------------------------
if (-not (Test-Path "$ProjectRoot\manage.py")) {
    Write-Host "ERROR: manage.py not found in project root." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PipfilePath)) {
    Write-Host "ERROR: Pipfile not found in project root." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Windows Terminal (wt.exe) not found." -ForegroundColor Red
    exit 1
}

# ----------------------------------------------------------
# FORCE PIPENV TO USE CORRECT PIPFILE
# ----------------------------------------------------------
$env:PIPENV_PIPFILE = $PipfilePath

# ----------------------------------------------------------
# VERIFY DJANGO ENVIRONMENT
# ----------------------------------------------------------
Write-Host "Verifying Django configuration..." -ForegroundColor Magenta
pipenv run python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','shwetDhara_project.settings'); import django; django.setup()" 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Django environment validation failed." -ForegroundColor Red
    exit 1
}

Write-Host "Django OK" -ForegroundColor Green

# ----------------------------------------------------------
# REDIS CHECK AND START
# ----------------------------------------------------------
Write-Host "Checking Redis service..." -ForegroundColor Magenta
redis-cli ping 2>$null | Out-Null

if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path $RedisExePath)) {
        Write-Host "ERROR: Redis executable not found." -ForegroundColor Red
        exit 1
    }

    Write-Host "Starting Redis server..." -ForegroundColor Yellow
    Get-Process redis-server -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
    Start-Process $RedisExePath -WindowStyle Hidden
    Start-Sleep -Seconds 5

    redis-cli ping 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start Redis." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Redis OK" -ForegroundColor Green

# ----------------------------------------------------------
# CLEAR OLD CELERY PIDS
# ----------------------------------------------------------
Write-Host "Cleaning up old Celery processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*celery*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# ----------------------------------------------------------
# CHECK MESSAGE QUEUE STATUS
# ----------------------------------------------------------
Write-Host "Checking message queue status..." -ForegroundColor Magenta
$queueCheck = pipenv run python -c @"
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
import django
django.setup()

from django.utils import timezone
from main_app.models import MessageQueue

stale_time = timezone.now() - timezone.timedelta(minutes=5)

print("📊 Message Queue Status:")
print("   Pending:", MessageQueue.objects.filter(status="PENDING").count())
print("   Retry:", MessageQueue.objects.filter(status="RETRY").count())
print("   Stuck:", MessageQueue.objects.filter(
    status="PROCESSING",
    processing_started_at__lt=stale_time
).count())
"@ 2>&1


Write-Host $queueCheck

# ----------------------------------------------------------
# BUILD WINDOWS TERMINAL COMMANDS (FIXED)
# ----------------------------------------------------------
$timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$machineName = $env:COMPUTERNAME

$messageWorkerName = "message_worker_${timestamp}_${machineName}"
$generalWorkerName = "general_worker_${timestamp}_${machineName}"

# WhatsApp MONITOR Service tab (MONITOR ONLY)
$whatsappMonitorTab = "new-tab --title `"WhatsApp Monitor`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && set PYTHONPATH=$ProjectRoot && pipenv run python main_app/whatsapp_monitor_service.py`""

# ✅ SAFE ARRAY-BASED COMMAND BUILD
$wtCommand = @(
    "new-tab --title `"Django Server`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && pipenv run python manage.py runserver`""
    "new-tab --title `"Celery Beat`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && pipenv run celery -A shwetDhara_project beat --loglevel=INFO`""
    "new-tab --title `"Message Queue Worker`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && pipenv run celery -A shwetDhara_project worker -Q message_queue --concurrency=1 --pool=solo --loglevel=INFO -n $messageWorkerName`""
    "new-tab --title `"General Worker`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && pipenv run celery -A shwetDhara_project worker --loglevel=INFO --concurrency=2 --pool=solo -n $generalWorkerName`""
    $whatsappMonitorTab
) -join " ; "

# ----------------------------------------------------------
# LAUNCH WINDOWS TERMINAL
# ----------------------------------------------------------
Write-Host ""
Write-Host "Starting services in Windows Terminal..." -ForegroundColor Magenta
Write-Host "Message Queue Worker Name: $messageWorkerName" -ForegroundColor Cyan
Write-Host "General Worker Name: $generalWorkerName" -ForegroundColor Cyan
Write-Host "WhatsApp Monitor: Tab 5 (MONITOR ONLY)" -ForegroundColor Cyan

Start-Process wt.exe -ArgumentList $wtCommand

# ----------------------------------------------------------
# FINAL STATUS
# ----------------------------------------------------------
Start-Sleep -Seconds 8
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ALL SERVICES STARTED SUCCESSFULLY" -ForegroundColor Green
Write-Host "Django URL: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
