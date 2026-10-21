# UTF-8 banners and log lines for stage4_eval PowerShell wrappers.

function Write-Stage4TeeLine {
    param([string]$Text)
    if ($null -eq $Text) { return }
    Write-Host $Text
    if ($env:STAGE4_RUN_LOG) {
        $dir = Split-Path -Parent $env:STAGE4_RUN_LOG
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        Add-Content -Path $env:STAGE4_RUN_LOG -Value $Text -Encoding utf8
    }
}

function Invoke-Stage4Python {
    <#
    Запуск Python с потоковым tee stdout/stderr в консоль и STAGE4_RUN_LOG.
    Требует $Python из _root.ps1. Включает STAGE4_LOG_TEE, чтобы stage4_console
    не дублировал строки в файл (запись только через tee).
    #>
    param(
        [Parameter(Mandatory)]
        [string[]]$ArgumentList
    )

    if (-not $Python) {
        throw "Invoke-Stage4Python: переменная Python не задана (подключите _root.ps1)."
    }

    $prevTee = $env:STAGE4_LOG_TEE
    $env:STAGE4_LOG_TEE = "1"
    $eventSubs = @()
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Python
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
        $argString = (
            @("-u") + $ArgumentList | ForEach-Object {
                if ($_ -match '[\s"]') { '"' + ($_.Replace('"', '""')) + '"' } else { $_ }
            }
        ) -join " "
        $psi.Arguments = $argString

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi

        $eventSubs += Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
            $line = $Event.SourceEventArgs.Data
            if ($line) { Write-Stage4TeeLine $line }
        }
        $eventSubs += Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
            $line = $Event.SourceEventArgs.Data
            if ($line) { Write-Stage4TeeLine $line }
        }

        [void]$proc.Start()
        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()
        $proc.WaitForExit()
        return $proc.ExitCode
    }
    finally {
        foreach ($sub in $eventSubs) {
            Unregister-Event -SubscriptionId $sub.Id -ErrorAction SilentlyContinue
            if ($sub.SourceIdentifier) {
                Remove-Event -SourceIdentifier $sub.SourceIdentifier -ErrorAction SilentlyContinue
            }
        }
        if ($null -eq $prevTee) {
            Remove-Item Env:STAGE4_LOG_TEE -ErrorAction SilentlyContinue
        }
        else {
            $env:STAGE4_LOG_TEE = $prevTee
        }
    }
}

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
