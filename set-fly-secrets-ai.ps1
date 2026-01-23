# Set Fly.io Secrets for AI Service

Write-Host "Setting up Fly.io secrets for CrownDesk AI Service..." -ForegroundColor Cyan
Write-Host ""

$secrets = @{
    "RETELL_API_KEY" = "key_6de437a9cc92176ec6bfdd0c9af2"
    "ELEVENLABS_API_KEY" = "your_elevenlabs_api_key_here"  # TODO: Replace with real key
    "BACKEND_URL" = "https://cdapi.xaltrax.com"
    "BACKEND_API_KEY" = "your_backend_api_key_here"  # TODO: Replace with real key
}

Write-Host "Secrets to set:" -ForegroundColor Yellow
foreach ($key in $secrets.Keys) {
    if ($secrets[$key] -like "*your_*") {
        Write-Host "  ❌ $key = $($secrets[$key])" -ForegroundColor Red
    } else {
        Write-Host "  ✅ $key = $($secrets[$key].Substring(0, [Math]::Min(20, $secrets[$key].Length)))..." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Commands to run (install Fly CLI first if needed):" -ForegroundColor Yellow
Write-Host ""
Write-Host "# Install Fly CLI (if not installed)" -ForegroundColor Cyan
Write-Host "iwr https://fly.io/install.ps1 -useb | iex" -ForegroundColor White
Write-Host ""
Write-Host "# Set secrets" -ForegroundColor Cyan
foreach ($key in $secrets.Keys) {
    Write-Host "fly secrets set $key=`"$($secrets[$key])`" -a crowndesk-ai-service" -ForegroundColor White
}
Write-Host ""
Write-Host "# Or set all at once:" -ForegroundColor Cyan
$secretString = ($secrets.GetEnumerator() | ForEach-Object { "$($_.Key)=`"$($_.Value)`"" }) -join " "
Write-Host "fly secrets set $secretString -a crowndesk-ai-service" -ForegroundColor White
Write-Host ""

Write-Host "After setting secrets, verify:" -ForegroundColor Yellow
Write-Host "fly secrets list -a crowndesk-ai-service" -ForegroundColor White
Write-Host ""

Write-Host "TODO: Get these keys from:" -ForegroundColor Yellow
Write-Host "  • ElevenLabs: https://elevenlabs.io/app/settings/api-keys" -ForegroundColor White
Write-Host "  • Backend API Key: From backend .env or Vercel" -ForegroundColor White
