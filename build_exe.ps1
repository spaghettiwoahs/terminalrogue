param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Expected project virtualenv at .venv\\Scripts\\python.exe"
}

if ($Clean) {
    if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
    if (Test-Path ".\dist") { Remove-Item ".\dist" -Recurse -Force }
}

& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check pyinstaller
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm ".\TerminalRogue.spec"

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $root\dist\TerminalRogue\TerminalRogue.exe"
