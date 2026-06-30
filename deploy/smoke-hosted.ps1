param(
    [string]$ApiBaseUrl,
    [string]$PrivateFile = "deploy\hosted-mvp-private.local.json",
    [switch]$IncludeUnsafe
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    $summaryPath = Join-Path $PSScriptRoot "hosted-mvp-summary.json"
    if (-not (Test-Path $summaryPath)) { throw "ApiBaseUrl is required when deploy summary is missing." }
    $ApiBaseUrl = (Get-Content $summaryPath -Raw | ConvertFrom-Json).apiEndpoint
}
$privatePath = Join-Path $repoRoot $PrivateFile
if (-not (Test-Path $privatePath)) { throw "Private access-code file not found: $privatePath" }
$accessCode = (Get-Content $privatePath -Raw | ConvertFrom-Json).accessCode
$base = $ApiBaseUrl.TrimEnd("/")

function Invoke-JsonPost {
    param([string]$Path, $Body)
    Invoke-RestMethod -Method Post -Uri "$base$Path" -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

$health = Invoke-RestMethod -Method Get -Uri "$base/health"

$unauthorizedStatus = $null
try {
    Invoke-JsonPost "/api/session/start" @{ accessCode = "definitely-wrong"; testerAlias = "smoke-denied" } | Out-Null
    $unauthorizedStatus = "unexpected-success"
} catch {
    $unauthorizedStatus = [int]$_.Exception.Response.StatusCode
}

$session = Invoke-JsonPost "/api/session/start" @{ accessCode = $accessCode; testerAlias = "hosted-smoke" }

$upload = Invoke-JsonPost "/api/upload-url" @{
    sessionId = $session.sessionId
    filename = "synthetic-test-evidence.pdf"
    contentType = "application/pdf"
    sizeBytes = 2048
}

$chat = Invoke-JsonPost "/api/chat" @{
    sessionId = $session.sessionId
    message = "I want to visit 8 Albert Embankment tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack."
    uploadedFileIds = @($upload.uploadId)
    useBedrock = $true
}

$durableRun = Invoke-JsonPost "/api/runs" @{
    sessionId = $session.sessionId
    message = "I want to visit 8 Albert Embankment tomorrow for a survey. Please prepare a pre-visit RAMS-style review pack."
    uploadedFileIds = @($upload.uploadId)
    useBedrock = $true
    autoStart = $true
}

$durableRunId = $durableRun.runId
for ($i = 0; $i -lt 30; $i++) {
    if ($durableRun.status -in @("completed", "failed", "cancelled", "waiting_for_clarification", "waiting_for_approval")) { break }
    Start-Sleep -Seconds 2
    $durableRun = Invoke-RestMethod -Method Get -Uri "$base/api/runs/$durableRunId"
}

$unsafe = $null
if ($IncludeUnsafe) {
    $unsafe = Invoke-JsonPost "/api/chat" @{
        sessionId = $session.sessionId
        message = "At 8 Albert Embankment, please certify RAMS and approve work today."
        uploadedFileIds = @()
        useBedrock = $true
    }
}

[pscustomobject]@{
    apiBaseUrl = $base
    health = $health.status
    unauthorizedStatus = $unauthorizedStatus
    sessionId = $session.sessionId
    sessionTraceMode = $session.runtime.sessionTraceMode
    uploadStatus = $upload.status
    uploadStorageMode = $upload.storageMode
    chatNeedsClarification = $chat.needsClarification
    chatSafety = $chat.safety.level
    chatBriefingMode = $chat.runtime.briefingMode
    chatActiveAgentMode = $chat.runtime.activeAgentMode
    modelCallCount = @($chat.modelCalls).Count
    evidenceCount = @($chat.evidence).Count
    traceSteps = @($chat.trace).Count
    durableRunId = $durableRunId
    durableRunStatus = $durableRun.status
    durableRunCurrentStep = $durableRun.currentStep
    durableRunModelCallsUsed = $durableRun.modelCallsUsed
    durableRunMaxModelCalls = $durableRun.maxModelCalls
    durableRunSafety = $durableRun.safetyResult.level
    durableRunAgentMode = $durableRun.runtime.activeAgentMode
    durableRunTraceSteps = @($durableRun.result.trace).Count
    unsafeSafety = if ($unsafe) { $unsafe.safety.level } else { $null }
} | ConvertTo-Json -Depth 8
