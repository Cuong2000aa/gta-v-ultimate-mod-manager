$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller --noconfirm --clean "packaging/windows.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $root "dist/GtaVUltimateModManager.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Build completed without producing $exe"
}

$sizeMb = [Math]::Round((Get-Item -LiteralPath $exe).Length / 1MB, 1)
Write-Host "Built $exe ($sizeMb MB)"
