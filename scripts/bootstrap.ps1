param(
    [string]$WorkDir = (Get-Location).Path,
    [string]$Python = 'python',
    [string]$AssetsFrom = '',
    [switch]$Offline,
    [switch]$AllowDownload
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
$workRoot = [System.IO.Path]::GetFullPath($WorkDir)
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
$venvRoot = Join-Path $workRoot '.notability-venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
$requirements = Join-Path $skillRoot 'requirements.txt'
& $venvPython -c "import sys; assert sys.version_info[:2] == (3,12), 'This locked runtime requires CPython 3.12.'"
if ($LASTEXITCODE -ne 0) { throw 'Use CPython 3.12 with -Python <path-to-python>.' }
$wheelhouse = Join-Path $skillRoot 'wheelhouse'
& $venvPython -m pip install --no-cache-dir --no-index --find-links $wheelhouse -r $requirements
if ($LASTEXITCODE -ne 0) {
    if (-not $AllowDownload) {
        throw 'Offline dependency installation failed. Bundled wheels target CPython 3.12 / Windows x64. Use -AllowDownload for another compatible Python/platform.'
    }
    & $venvPython -m pip install --no-cache-dir -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$assetArguments = @((Join-Path $PSScriptRoot 'restore_assets.py'))
if ($AssetsFrom) { $assetArguments += @('--from-repository', $AssetsFrom) }
if (-not $Offline) { $assetArguments += '--download' }
& $venvPython @assetArguments
if ($LASTEXITCODE -ne 0) { throw 'Could not restore verified upstream assets.' }
& $venvPython (Join-Path $PSScriptRoot 'doctor.py')
if ($LASTEXITCODE -ne 0) { throw 'The rendering environment did not pass its checks.' }
Write-Output "NOTABILITY_PYTHON=$venvPython"
