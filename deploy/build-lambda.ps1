param(
    [string]$OutputZip = ".deploy-build\3d-rams-lambda.zip"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$buildRoot = Join-Path $repoRoot ".deploy-build"
$packageRoot = Join-Path $buildRoot "lambda-package"
$wheelhouse = Join-Path $buildRoot "wheelhouse"
$requirements = Join-Path $PSScriptRoot "lambda-requirements.txt"
$zipPath = Join-Path $repoRoot $OutputZip

if (Test-Path $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
if (Test-Path $wheelhouse) { Remove-Item -LiteralPath $wheelhouse -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot, $wheelhouse | Out-Null

python -m pip download `
    --only-binary=:all: `
    --platform manylinux2014_x86_64 `
    --python-version 311 `
    --implementation cp `
    --abi cp311 `
    --requirement $requirements `
    --dest $wheelhouse `
    --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip download failed; Lambda package was not built." }

python -m pip install `
    --only-binary=:all: `
    --platform manylinux2014_x86_64 `
    --python-version 311 `
    --implementation cp `
    --abi cp311 `
    --no-index `
    --find-links $wheelhouse `
    --requirement $requirements `
    --target $packageRoot `
    --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install failed; Lambda package was not built." }

Copy-Item -Path (Join-Path $repoRoot "backend") -Destination (Join-Path $packageRoot "backend") -Recurse
Copy-Item -Path (Join-Path $repoRoot "fixtures") -Destination (Join-Path $packageRoot "fixtures") -Recurse

if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

$zipItem = Get-Item $zipPath
[pscustomobject]@{
    zipPath = $zipItem.FullName
    sizeBytes = $zipItem.Length
    sizeMB = [math]::Round($zipItem.Length / 1MB, 2)
} | ConvertTo-Json
