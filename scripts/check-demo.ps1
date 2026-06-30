param(
    [switch]$Install,
    [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir
if (-not $env:PYTHONPYCACHEPREFIX) {
    $env:PYTHONPYCACHEPREFIX = Join-Path ([System.IO.Path]::GetTempPath()) "3d-rams-pycache"
}

if ($Install) {
    Write-Host "Installing AgentCore Python package"
    & $PythonBin -m pip install --disable-pip-version-check -e app/rams_supervisor_runtime

    Write-Host "Installing frontend dependencies"
    Push-Location frontend
    try {
        if (Test-Path package-lock.json) {
            npm.cmd ci
        }
        else {
            npm.cmd install
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Compiling AgentCore package, tests, and scripts"
& $PythonBin -m compileall `
    app/rams_agent_tools `
    app/asi_one_entry_agent `
    app/rams_supervisor_runtime/main.py `
    app/rams_supervisor_runtime/mcp_client `
    app/rams_supervisor_runtime/model `
    app/rams_supervisor_runtime/skills `
    app/rams_supervisor_runtime/tests `
    app/rams_supervisor_runtime/supervisor_core `
    agentverse `
    scripts

Write-Host "Running AgentCore workflow and invocation tests"
& $PythonBin -m unittest discover -s app/rams_supervisor_runtime/tests -q

Write-Host "Running entry-agent supervisor adapter tests"
& $PythonBin -m unittest discover -s app/asi_one_entry_agent/tests -q

Write-Host "Running AgentVerse proxy boundary tests"
& $PythonBin -m unittest discover -s agentverse/tests -q

Write-Host "Running deterministic no-AWS demo evaluation"
$previousEnableBedrock = [Environment]::GetEnvironmentVariable("ENABLE_BEDROCK", "Process")
[Environment]::SetEnvironmentVariable("ENABLE_BEDROCK", "false", "Process")
try {
    & $PythonBin scripts/evaluate-demo.py
}
finally {
    [Environment]::SetEnvironmentVariable("ENABLE_BEDROCK", $previousEnableBedrock, "Process")
}

Write-Host "Building frontend"
if (-not (Test-Path frontend/node_modules)) {
    throw "frontend/node_modules is missing. Run: powershell -ExecutionPolicy Bypass -File scripts/check-demo.ps1 -Install"
}

Push-Location frontend
try {
    npm.cmd run build
}
finally {
    Pop-Location
}

Write-Host "Running AgentCore/frontend HTTP runtime smoke test"
& $PythonBin scripts/smoke-runtime.py

Write-Host "3D-RAMS local verification passed."
