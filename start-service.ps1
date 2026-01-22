# Start AI Service with proper Python path
# This ensures the ai_service module can be found

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting AI Service (FastAPI)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set Python path to include src directory
$env:PYTHONPATH = "src"

# Check if .env file exists
if (Test-Path ".env") {
    Write-Host "✅ .env file found" -ForegroundColor Green
    
    # Check for required keys
    $envContent = Get-Content ".env" -Raw
    
    if ($envContent -match "OPENAI_API_KEY") {
        Write-Host "✅ OPENAI_API_KEY configured" -ForegroundColor Green
    } else {
        Write-Host "⚠️  OPENAI_API_KEY not found in .env" -ForegroundColor Yellow
    }
    
    if ($envContent -match "ELEVENLABS_API_KEY") {
        Write-Host "✅ ELEVENLABS_API_KEY configured" -ForegroundColor Green
    } else {
        Write-Host "⚠️  ELEVENLABS_API_KEY not found in .env" -ForegroundColor Yellow
        Write-Host "   Add: ELEVENLABS_API_KEY=your_key_here" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  .env file not found" -ForegroundColor Yellow
    Write-Host "   Create apps/ai-service/.env with:" -ForegroundColor Gray
    Write-Host "   OPENAI_API_KEY=your_key" -ForegroundColor White
    Write-Host "   ELEVENLABS_API_KEY=your_key" -ForegroundColor White
}

Write-Host ""
Write-Host "Starting FastAPI server on http://127.0.0.1:8001 ..." -ForegroundColor Cyan
Write-Host ""

# Start uvicorn with correct module path
python -m uvicorn ai_service.main:app --reload --port 8001
