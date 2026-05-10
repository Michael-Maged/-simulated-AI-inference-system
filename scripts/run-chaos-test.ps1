<#
.SYNOPSIS
    Scripted chaos test that produces clean CSV + a markdown timeline for the report.
.DESCRIPTION
    Starts a Locust load run as a background process, lets it reach steady state,
    kills a Swarm worker mid-test, waits for the heartbeat-timeout window,
    recovers the worker, then waits for the load test to finish. Captures:

    1. docs/results/chaos_run_stats*.csv  (Locust output)
    2. docs/results/chaos_timeline.md     (event timeline with timestamps and worker counts)

    Section 8.6 of the project report can ingest both directly.

    Run from project root:
        .\scripts\run-chaos-test.ps1
        .\scripts\run-chaos-test.ps1 -Users 200 -Duration 240
.PARAMETER TargetHost
    Base URL of the load balancer.
.PARAMETER Users
    Concurrent Locust users during the chaos run.
.PARAMETER Duration
    Total test duration in seconds.
.PARAMETER KillAt
    Seconds after start when the worker is killed.
.PARAMETER RecoverAt
    Seconds after start when the worker is restored.
.PARAMETER ResultsDir
    Where to write CSVs and timeline.
#>
param(
    [string]$TargetHost = "http://localhost:8000",
    [int]$Users = 100,
    [int]$Duration = 180,
    [int]$KillAt = 45,
    [int]$RecoverAt = 105,
    [string]$ResultsDir = "docs/results"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
}

$csvPrefix   = Join-Path $ResultsDir "chaos_run"
$timelinePath = Join-Path $ResultsDir "chaos_timeline.md"

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
$start = Get-Date
function T {
    param()
    $elapsed = [int]((Get-Date) - $start).TotalSeconds
    return "T+{0,3}s" -f $elapsed
}

$timeline = @()
function Log-Event {
    param([string]$msg, [string]$detail = "")
    $line = "$(T) | $msg"
    if ($detail) { $line = "$line | $detail" }
    Write-Host $line -ForegroundColor Cyan
    $script:timeline += $line
}

function Get-WorkerStatus {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8001/workers" -TimeoutSec 5
        $alive = ($resp | Where-Object { $_.alive -eq $true }).Count
        $total = $resp.Count
        return "$alive / $total alive"
    } catch {
        return "n/a (master unreachable)"
    }
}

function Get-SwarmReplicas {
    try {
        $line = (& docker service ls --filter "name=inference_worker" --format "{{.Replicas}}" 2>$null)
        if ($line) { return $line.Trim() } else { return "n/a" }
    } catch {
        return "n/a"
    }
}

# ----------------------------------------------------------------------
# Pre-flight
# ----------------------------------------------------------------------
Log-Event "Chaos test starting" "host=$TargetHost users=$Users duration=${Duration}s"
Log-Event "Pre-test worker status" (Get-WorkerStatus)
Log-Event "Pre-test Swarm replicas" (Get-SwarmReplicas)

# ----------------------------------------------------------------------
# Kick off Locust in the background
# ----------------------------------------------------------------------
$locustArgs = @(
    "-f", "client/locustfile.py",
    "--host", $TargetHost,
    "-u", "$Users",
    "-r", "20",
    "-t", "${Duration}s",
    "--csv", $csvPrefix,
    "--headless",
    "--only-summary"
)
$locust = Start-Process -FilePath "locust" -ArgumentList $locustArgs -PassThru -NoNewWindow
Log-Event "Locust started" "pid=$($locust.Id)"

try {
    # 1. Wait for steady state
    Log-Event "Waiting for steady state ($KillAt s)"
    Start-Sleep -Seconds $KillAt

    # 2. Kill a worker
    Log-Event "Killing worker-2 via chaos.py"
    & python client/chaos.py --kill worker-2 2>&1 | ForEach-Object { Log-Event "chaos.py >" $_ }
    Log-Event "Worker status post-kill" (Get-WorkerStatus)

    # 3. Wait through the recovery window
    $waitForRecover = $RecoverAt - $KillAt
    Log-Event "Waiting $waitForRecover s in degraded state"
    Start-Sleep -Seconds 5
    Log-Event "Mid-degradation worker status" (Get-WorkerStatus)
    Start-Sleep -Seconds ($waitForRecover - 5)

    # 4. Recover
    Log-Event "Recovering worker-2 via chaos.py"
    & python client/chaos.py --recover worker-2 2>&1 | ForEach-Object { Log-Event "chaos.py >" $_ }
    Start-Sleep -Seconds 5
    Log-Event "Post-recover worker status" (Get-WorkerStatus)

    # 5. Wait for Locust to finish
    $remaining = $Duration - $RecoverAt
    Log-Event "Letting load test finish ($remaining s)"
    Wait-Process -Id $locust.Id -Timeout ($remaining + 30)
    Log-Event "Locust exited" "code=$($locust.ExitCode)"
} finally {
    if (-not $locust.HasExited) {
        Log-Event "Locust still running, terminating"
        Stop-Process -Id $locust.Id -Force
    }
}

Log-Event "Final worker status" (Get-WorkerStatus)
Log-Event "Chaos test complete"

# ----------------------------------------------------------------------
# Write timeline markdown
# ----------------------------------------------------------------------
$header = @(
    "# Chaos Test Timeline",
    ""
    "**Date:** $(Get-Date -Format 'yyyy-MM-dd HH:mm')  ",
    "**Target:** $TargetHost  ",
    "**Users:** $Users  Duration: ${Duration}s  Kill at T+${KillAt}s  Recover at T+${RecoverAt}s  ",
    "",
    "## Event log",
    ""
    "``````",
)
$footer = @(
    "``````",
    ""
    "## Files generated",
    "",
    "- ``${csvPrefix}_stats.csv`` (Locust aggregated stats)",
    "- ``${csvPrefix}_stats_history.csv`` (per-second time series)",
    "- ``${csvPrefix}_failures.csv`` (per-failure breakdown)",
    ""
    "## What to look for in Grafana",
    "",
    "- ``master_workers_healthy`` should drop by 1 a few seconds after the kill event",
    "  (heartbeat timeout window).",
    "- ``master_requests_failed_total`` should stay flat — retries absorb the failure.",
    "- ``lb_response_latency_seconds`` p95/p99 should spike during the kill window then return to baseline.",
    "- ``worker_infer_latency_seconds`` should show the killed worker's series end and resume on recover.",
    ""
)
$content = ($header + $timeline + $footer) -join "`r`n"
Set-Content -Path $timelinePath -Value $content
Log-Event "Wrote timeline" $timelinePath

Write-Host ""
Write-Host "===== Chaos test artefacts =====" -ForegroundColor Green
Write-Host "  $csvPrefix*.csv"
Write-Host "  $timelinePath"
