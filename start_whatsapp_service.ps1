# ==========================================================
# WHATSAPP DESKTOP SERVICE LAUNCHER
# Runs the WhatsApp Desktop automation service
# ==========================================================

$ProjectRoot = "C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
$PipfilePath = "$ProjectRoot\Pipfile"

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   WHATSAPP DESKTOP SERVICE LAUNCHER" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------
# VALIDATION
# ----------------------------------------------------------
if (-not (Test-Path "$ProjectRoot\manage.py")) {
    Write-Host "ERROR: manage.py not found" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PipfilePath)) {
    Write-Host "ERROR: Pipfile not found" -ForegroundColor Red
    exit 1
}

# ----------------------------------------------------------
# SET ENVIRONMENT
# ----------------------------------------------------------
$env:PIPENV_PIPFILE = $PipfilePath

# ----------------------------------------------------------
# CHECK WHATSAPP DESKTOP
# ----------------------------------------------------------
Write-Host "Checking WhatsApp Desktop..." -ForegroundColor Magenta
$whatsappProcess = Get-Process WhatsApp -ErrorAction SilentlyContinue

if (-not $whatsappProcess) {
    Write-Host "⚠️  WhatsApp Desktop is not running" -ForegroundColor Yellow
    Write-Host "   Starting WhatsApp Desktop..." -ForegroundColor Yellow
    
    # Try to start WhatsApp Desktop
    $whatsappPaths = @(
        "$env:LOCALAPPDATA\WhatsApp\WhatsApp.exe",
        "C:\Program Files\WhatsApp\WhatsApp.exe",
        "C:\Program Files (x86)\WhatsApp\WhatsApp.exe"
    )
    
    $started = $false
    foreach ($path in $whatsappPaths) {
        if (Test-Path $path) {
            Start-Process $path
            Write-Host "   Started from: $path" -ForegroundColor Green
            $started = $true
            Start-Sleep -Seconds 5
            break
        }
    }
    
    if (-not $started) {
        Write-Host "   Could not find WhatsApp Desktop" -ForegroundColor Yellow
        Write-Host "   Please open WhatsApp Desktop manually" -ForegroundColor Yellow
    }
} else {
    Write-Host "✅ WhatsApp Desktop is running" -ForegroundColor Green
}

# ----------------------------------------------------------
# VERIFY DATABASE CONNECTION
# ----------------------------------------------------------
Write-Host "Checking database connection..." -ForegroundColor Magenta
pipenv run python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
import django
django.setup()
from django.db import connection
try:
    connection.ensure_connection()
    print('Database connection OK')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Database connection failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Database connection OK" -ForegroundColor Green

# ----------------------------------------------------------
# START WHATSAPP SERVICE
# ----------------------------------------------------------
Write-Host ""
Write-Host "Starting WhatsApp Desktop Service..." -ForegroundColor Magenta
Write-Host "This will run in a new terminal window" -ForegroundColor Cyan

$wtCommand = "new-tab --title `"WhatsApp Service`" cmd /k `"cd /d $ProjectRoot && set PIPENV_PIPFILE=$PipfilePath && pipenv run python main_app/whatsapp_desktop_service.py`""

Start-Process wt.exe -ArgumentList $wtCommand

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ WHATSAPP SERVICE STARTED" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT NOTES:" -ForegroundColor Yellow
Write-Host "1. WhatsApp Desktop MUST be open and logged in" -ForegroundColor White
Write-Host "2. Do NOT lock your computer screen" -ForegroundColor White
Write-Host "3. Service will auto-send messages when created" -ForegroundColor White
Write-Host "4. Check logs at: $ProjectRoot\whatsapp_service.log" -ForegroundColor White
Write-Host ""
Write-Host "To test:" -ForegroundColor Magenta
Write-Host "1. Create an Advance Sale in Django admin" -ForegroundColor White
Write-Host "2. System will queue WhatsApp messages" -ForegroundColor White
Write-Host "3. This service will send them automatically" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan