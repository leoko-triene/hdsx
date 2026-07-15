$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

function Find-Python {
    $candidates = @()

    if ($env:LLM_LEARN_PYTHON -and (Test-Path -LiteralPath $env:LLM_LEARN_PYTHON)) {
        $candidates += $env:LLM_LEARN_PYTHON
    }

    $condaRoots = @(
        $env:CONDA_PREFIX,
        "D:\miniconda",
        "D:\anaconda3",
        "D:\anaconda"
    )
    $envNames = @("llm_learn", "program-hd")

    foreach ($root in $condaRoots) {
        if (-not $root) { continue }
        foreach ($name in $envNames) {
            $candidates += Join-Path $root "envs\$name\python.exe"
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    throw "找不到可用的 Python。请先执行 conda activate llm_learn 或 program-hd，或设置 LLM_LEARN_PYTHON。"
}

Write-Host "使用 Python: $python"
& $python -m uvicorn app.main:app --reload --reload-dir backend --app-dir backend
