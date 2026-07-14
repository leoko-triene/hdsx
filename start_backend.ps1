$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$python = $null
if ($env:CONDA_DEFAULT_ENV -eq "llm_learn") {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source }
}

if (-not $python -and $env:LLM_LEARN_PYTHON -and (Test-Path -LiteralPath $env:LLM_LEARN_PYTHON)) {
    $python = $env:LLM_LEARN_PYTHON
}

$knownPython = "D:\anaconda\envs\llm_learn\python.exe"
if (-not $python -and (Test-Path -LiteralPath $knownPython)) {
    $python = $knownPython
}

if (-not $python) {
    throw "找不到 llm_learn Python。请先执行 conda activate llm_learn，或设置 LLM_LEARN_PYTHON。"
}

Write-Host "使用 Python: $python"
& $python -m uvicorn app.main:app --reload --reload-dir backend --app-dir backend
