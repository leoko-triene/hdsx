$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $projectRoot ".runtime\node-v24.18.0-win-x64"
$python = "D:\anaconda\envs\llm_learn\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "llm_learn Python not found. Set up the configured Conda environment first."
}
if (-not (Test-Path -LiteralPath (Join-Path $nodeDir "node.exe"))) {
    throw "Portable Node runtime not found. See README."
}

Set-Location -LiteralPath (Join-Path $projectRoot "frontend")
& "$nodeDir\node.exe" ".\node_modules\vue-tsc\bin\vue-tsc.js" -b
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$nodeDir\node.exe" ".\node_modules\vite\bin\vite.js" build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location -LiteralPath $projectRoot
$env:SERVE_FRONTEND = "true"
$env:APP_DEBUG = "false"
Write-Host "Production service: http://0.0.0.0:8000"
& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --app-dir backend
