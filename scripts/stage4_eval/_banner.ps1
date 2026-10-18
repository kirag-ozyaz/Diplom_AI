# UTF-8 banners and log lines for stage4_eval PowerShell wrappers.
function Write-Stage4Log {
    param([string]$Message)
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    if ($env:STAGE4_RUN_LOG) {
        $dir = Split-Path -Parent $env:STAGE4_RUN_LOG
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        Add-Content -Path $env:STAGE4_RUN_LOG -Value $line -Encoding utf8
    }
}

function Write-Stage4Banner {
    param(
        [string]$Title,
        [string]$Detail = "",
        [string]$Step = ""
    )
    if (-not $Step -and $env:STAGE4_BANNER_STEP) {
        $Step = $env:STAGE4_BANNER_STEP
    }
    $line = if ($Step) { "$Step $Title" } else { $Title }
    Write-Stage4Log ("=" * 60)
    Write-Stage4Log $line
    Write-Stage4Log ("=" * 60)
    if ($Detail) {
        $d = if ($Detail.StartsWith("Этап:")) { $Detail } else { "Этап: $Detail" }
        Write-Stage4Log "[*] $d"
    }
}
