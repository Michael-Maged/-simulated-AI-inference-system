<#
.SYNOPSIS
    Run the full Locust load test sweep against a running stack.
.DESCRIPTION
    Runs four sequential Locust scenarios at 50, 100, 500, and 1000 concurrent users
    plus a warmup phase. Outputs CSV stats files into docs/results/ for the report.

    Each scenario uses --headless mode with a per-test duration that gives the
    semantic cache time to warm and the worker pool time to reach steady state.

    Run from the project root in PowerShell with the venv activated:
        .\scripts\run-load-tests.ps1
        .\scripts\run-load-tests.ps1 -Host http://localhost:8000 -SkipWarmup
.PARAMETER TargetHost
    Base URL of the load balancer. Defaults to http://localhost:8000.
.PARAMETER ResultsDir
    Where to write CSVs. Defaults to docs/results.
.PARAMETER SkipWarmup
    Skip the 30s cache-warmup phase. Useful for rerunning a single scenario.
.PARAMETER Scenarios
    Subset of scenarios to run. Default: all (50,100,500,1000).
#>
param(
    [string]$TargetHost = "http://localhost:8000",
    [string]$ResultsDir = "docs/results",
    [switch]$SkipWarmup,
    [int[]]$Scenarios = @(50, 100, 500, 1000)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
}

function Invoke-LocustRun {
    param(
        [int]$Users,
        [int]$RampRate,
        [string]$Duration,
        [string]$Tag
    )
    $csvPrefix = Join-Path $ResultsDir $Tag
    Write-Host ""
    Write-Host "===== Running $Tag : $Users users, ramp $RampRate/s, duration $Duration =====" -ForegroundColor Cyan
    & locust -f client/locustfile.py `
        --host $TargetHost `
        -u $Users `
        -r $RampRate `
        -t $Duration `
        --csv $csvPrefix `
        --headless `
        --only-summary
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Locust exited with code $LASTEXITCODE for $Tag" -ForegroundColor Red
        throw "Load test $Tag failed."
    }
    Write-Host "Saved $csvPrefix*.csv" -ForegroundColor Green
}

# 0. Warm the cache so the headline numbers reflect steady state
if (-not $SkipWarmup) {
    Invoke-LocustRun -Users 20 -RampRate 5 -Duration "30s" -Tag "warmup"
}

# Scenario plan: (users, ramp_rate, duration_seconds, tag)
$plan = @{
    50   = @(50,  10,  "60s",  "scale_50u")
    100  = @(100, 20,  "90s",  "scale_100u")
    500  = @(500, 50,  "120s", "scale_500u")
    1000 = @(1000,100, "180s", "scale_1000u")
}

foreach ($u in $Scenarios) {
    if (-not $plan.ContainsKey($u)) {
        Write-Host "Unknown scenario: $u users (valid: 50, 100, 500, 1000)" -ForegroundColor Yellow
        continue
    }
    $args = $plan[$u]
    Invoke-LocustRun -Users $args[0] -RampRate $args[1] -Duration $args[2] -Tag $args[3]
    Write-Host "Cooling for 15s before next scenario..."
    Start-Sleep -Seconds 15
}

Write-Host ""
Write-Host "===== Load test sweep complete =====" -ForegroundColor Green
Write-Host "Results in $ResultsDir" -ForegroundColor Green
Write-Host "Generate plots:  python client/plot_results.py --csv-prefix $ResultsDir/scale_1000u --out $ResultsDir/" -ForegroundColor Yellow
