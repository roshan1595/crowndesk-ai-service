# CrownDesk AI Service - Python Environment Setup
# Run this script to set up the Python virtual environment

$ErrorActionPreference = "Stop"
$AI_SERVICE_DIR = $PSScriptRoot | Split-Path -Parent
$VENV_PATH = Join-Path $AI_SERVICE_DIR ".venv"

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  CrownDesk AI Service - Python Setup" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check for Python 3.12 or 3.11
$pythonCmd = $null

# Try py launcher first
$pyVersions = py -0 2>&1
if ($pyVersions -match "3\.12") {
    $pythonCmd = "py -3.12"
    Write-Host "  [OK] Found Python 3.12 via py launcher" -ForegroundColor Green
} elseif ($pyVersions -match "3\.11") {
    $pythonCmd = "py -3.11"
    Write-Host "  [OK] Found Python 3.11 via py launcher" -ForegroundColor Green
}

# Try direct commands
if (-not $pythonCmd) {
    if (Get-Command python3.12 -ErrorAction SilentlyContinue) {
        $pythonCmd = "python3.12"
        Write-Host "  [OK] Found python3.12" -ForegroundColor Green
    } elseif (Get-Command python3.11 -ErrorAction SilentlyContinue) {
        $pythonCmd = "python3.11"
        Write-Host "  [OK] Found python3.11" -ForegroundColor Green
    }
}

# Check common installation paths on Windows
if (-not $pythonCmd) {
    $commonPaths = @(
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            $pythonCmd = $path
            Write-Host "  [OK] Found Python at $path" -ForegroundColor Green
            break
        }
    }
}

if (-not $pythonCmd) {
    Write-Host "  [ERROR] Python 3.11 or 3.12 not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please install Python 3.12:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 1: Download from python.org" -ForegroundColor White
    Write-Host "    https://www.python.org/downloads/release/python-3120/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Option 2: Use winget" -ForegroundColor White
    Write-Host "    winget install Python.Python.3.12" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Option 3: Use chocolatey" -ForegroundColor White
    Write-Host "    choco install python312" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  After installing, run this script again." -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "  Creating virtual environment at: $VENV_PATH" -ForegroundColor Yellow

if (Test-Path $VENV_PATH) {
    Write-Host "  [!] Virtual environment already exists. Removing..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VENV_PATH
}

$createVenvCmd = "$pythonCmd -m venv `"$VENV_PATH`""
Write-Host "  Running: $createVenvCmd" -ForegroundColor Gray
Invoke-Expression $createVenvCmd

if (-not (Test-Path "$VENV_PATH\Scripts\python.exe")) {
    Write-Host "  [ERROR] Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "  [OK] Virtual environment created" -ForegroundColor Green

# Activate and install dependencies
Write-Host ""
Write-Host "  Installing dependencies..." -ForegroundColor Yellow

$activateScript = Join-Path $VENV_PATH "Scripts\Activate.ps1"
& $activateScript

# Upgrade pip
& "$VENV_PATH\Scripts\python.exe" -m pip install --upgrade pip

# Install the package
Set-Location $AI_SERVICE_DIR
& "$VENV_PATH\Scripts\pip.exe" install -e ".[dev]"

Write-Host ""
Write-Host "  [OK] Dependencies installed" -ForegroundColor Green

# Verify installation
Write-Host ""
Write-Host "  Verifying installation..." -ForegroundColor Yellow
$pythonVersion = & "$VENV_PATH\Scripts\python.exe" --version
Write-Host "  Python version: $pythonVersion" -ForegroundColor Gray

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To activate the virtual environment:" -ForegroundColor White
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To start the AI service:" -ForegroundColor White
Write-Host "    cd apps\ai-service\src" -ForegroundColor Gray
Write-Host "    python -m uvicorn ai_service.main:app --port 8001 --reload" -ForegroundColor Cyan
Write-Host ""
