# Start Ollama in the background
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden

# Wait for Ollama to be ready
Write-Host "Starting Ollama..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($ready) {
    Write-Host "Ollama ready." -ForegroundColor Green
} else {
    Write-Host "Ollama may still be starting — continuing anyway." -ForegroundColor Yellow
}

# Launch the app
Write-Host "Starting Company Analyzer..." -ForegroundColor Cyan
streamlit run app.py
