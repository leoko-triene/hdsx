$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $projectRoot ".runtime\node-v24.18.0-win-x64"
$pnpm = Join-Path $nodeDir "pnpm.cmd"

if (-not (Test-Path -LiteralPath $pnpm)) {
    throw "Portable Node or pnpm is incomplete. See README."
}

$env:Path = "$nodeDir;$env:Path"
$env:COREPACK_HOME = Join-Path $projectRoot ".runtime\corepack"
Set-Location -LiteralPath (Join-Path $projectRoot "frontend")

$vite = Join-Path (Get-Location) "node_modules\vite\bin\vite.js"
if (-not (Test-Path -LiteralPath $vite)) {
    Write-Host "首次运行，正在安装前端依赖……"
    & $pnpm install --node-linker=hoisted
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "使用 Node: $nodeDir\node.exe"
& "$nodeDir\node.exe" $vite
