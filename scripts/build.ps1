$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $runtimeExe)) {
    throw "Ambiente .venv não encontrado. Crie-o explicitamente com Python 3.11 x86."
}

Push-Location $projectRoot
try {
    & $runtimeExe (Join-Path $projectRoot "scripts\check_runtime.py") --require-x86
    if ($LASTEXITCODE -ne 0) {
        throw "Build interrompido: use Python 3.11 x86."
    }

    & $runtimeExe -m ruff check src tests scripts
    if ($LASTEXITCODE -ne 0) {
        throw "Build interrompido: o lint falhou."
    }

    & $runtimeExe -m pytest -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) {
        throw "Build interrompido: os testes falharam."
    }

    & $runtimeExe -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "build.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller não concluiu o build."
    }

    Write-Host "Build de homologação criado em dist\SIAFSupportToolbox"
}
finally {
    Pop-Location
}
