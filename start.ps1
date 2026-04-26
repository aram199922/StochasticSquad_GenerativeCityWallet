# Generative City-Wallet - one-shot setup & launch
# Run from the repo root: .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Backend
Write-Host "[1/3] Installing backend dependencies..." -ForegroundColor Cyan
& "$root\venv\Scripts\pip.exe" install -r "$root\backend\requirements.txt" --quiet

if (-not (Test-Path "$root\backend\.env")) {
    Copy-Item "$root\backend\.env.example" "$root\backend\.env"
    Write-Host "  Created backend\.env (add API keys there - optional)" -ForegroundColor Yellow
}

Write-Host "[1/3] Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$backendCmd = "cd '$root\backend'; ..\venv\Scripts\uvicorn.exe main:app --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# 2. Mobile App
Write-Host "[2/3] Installing mobile-app dependencies..." -ForegroundColor Cyan
Set-Location "$root\mobile-app"
npm install --silent

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "[2/3] Starting Expo (web) on http://localhost:8081 ..." -ForegroundColor Cyan
$mobileCmd = "cd '$root\mobile-app'; npx expo start --web"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $mobileCmd

# 3. Merchant Dashboard
Write-Host "[3/3] Installing merchant-dashboard dependencies..." -ForegroundColor Cyan
Set-Location "$root\merchant-dashboard"
npm install --silent

if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.example" ".env.local"
}

Write-Host "[3/3] Starting dashboard on http://localhost:3000 ..." -ForegroundColor Cyan
$dashCmd = "cd '$root\merchant-dashboard'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $dashCmd

Set-Location $root

# Summary
Write-Host ""
Write-Host "All services starting in separate windows:" -ForegroundColor Green
Write-Host "  Backend API  ->  http://127.0.0.1:8000/docs"
Write-Host "  Mobile app   ->  http://localhost:8081"
Write-Host "  Dashboard    ->  http://localhost:3000"
