# Proverka CUDA: embeddings (PyTorch host) + Ollama (Docker GPU).
# Zapusk: powershell -ExecutionPolicy Bypass -File scripts\test_cudo.ps1

$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
$env:PYTHONIOENCODING = "utf-8"

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$fail = 0
$warn = 0

function Write-Result {
    param(
        [string]$Label,
        [ValidateSet("OK", "WARN", "FAIL")]
        [string]$Status,
        [string]$Detail = ""
    )
    $mark = switch ($Status) {
        "OK"   { "[OK]  " }
        "WARN" { "[WARN]" }
        "FAIL" { "[FAIL]" }
    }
    if ($Detail) {
        Write-Host ($mark + " " + $Label + " - " + $Detail)
    } else {
        Write-Host ($mark + " " + $Label)
    }
    if ($Status -eq "FAIL") { $script:fail++ }
    if ($Status -eq "WARN") { $script:warn++ }
}

Write-Host "=== CUDA / GPU ==="
Write-Host ("Project: " + $ProjectRoot)
Write-Host ""

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $smi = nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1
    if ($LASTEXITCODE -eq 0 -and $smi) {
        Write-Result "nvidia-smi" "OK" ($smi | Select-Object -First 1)
    } else {
        Write-Result "nvidia-smi" "FAIL" "no GPU data"
    }
} else {
    Write-Result "nvidia-smi" "FAIL" "not in PATH"
}

$torchHelper = Join-Path $PSScriptRoot "test_cudo_torch.py"
if (-not (Test-Path $torchHelper)) {
    Write-Result "PyTorch host" "FAIL" "missing test_cudo_torch.py"
} else {
    $torchOut = @(& $Python $torchHelper 2>&1 | ForEach-Object { "$_" })
    $torchExit = $LASTEXITCODE
    if ($torchExit -eq 0) {
        $ver = ($torchOut | Where-Object { $_ -match "^VERSION " }) -replace "^VERSION ", ""
        $dev = ($torchOut | Where-Object { $_ -match "^DEVICE " }) -replace "^DEVICE ", ""
        Write-Result "PyTorch host" "OK" ($ver + ", " + $dev)
    } elseif ($torchExit -eq 2) {
        Write-Result "PyTorch host" "FAIL" "import error"
    } else {
        $hint = ($torchOut | Where-Object { $_ -match "^HINT " }) -replace "^HINT ", ""
        $ver = ($torchOut | Where-Object { $_ -match "^VERSION " }) -replace "^VERSION ", ""
        Write-Result "PyTorch host" "FAIL" ($ver + " no CUDA. " + $hint)
    }
}

$dockerEngineOk = $false
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Result "Docker" "WARN" "not installed"
} else {
    $null = docker info 2>&1 | Out-Null
    $dockerEngineOk = ($LASTEXITCODE -eq 0)
    if (-not $dockerEngineOk) {
        Write-Result "Docker Engine" "FAIL" "unavailable - restart Docker Desktop"
    } else {
        $dockerInfo = docker info 2>&1 | Out-String
        if ($dockerInfo -match "nvidia") {
            Write-Result "Docker Engine" "OK" "nvidia runtime"
        } else {
            Write-Result "Docker Engine" "WARN" "no nvidia runtime, Ollama may use CPU"
        }
    }
}

if ($dockerCmd -and $dockerEngineOk) {
    $ollamaId = docker ps -q -f "name=^ollama$" 2>$null
    if (-not $ollamaId) {
        Write-Result "Ollama" "WARN" "not running - python scripts/start_ollama.py --pull"
    } else {
        Write-Result "Ollama" "OK" "container running"
        $gpuReq = docker inspect ollama --format "{{json .HostConfig.DeviceRequests}}" 2>&1
        if ($LASTEXITCODE -eq 0 -and $gpuReq -match "nvidia") {
            Write-Result "Ollama GPU compose" "OK" "nvidia DeviceRequests"
        } else {
            Write-Result "Ollama GPU compose" "FAIL" "no GPU - python scripts/start_ollama.py"
        }
        $smiIn = docker exec ollama nvidia-smi --query-gpu=name --format=csv,noheader 2>&1
        if ($LASTEXITCODE -eq 0 -and $smiIn -and ($smiIn -notmatch "error|not found")) {
            Write-Result "nvidia-smi in ollama" "OK" ($smiIn | Select-Object -First 1)
        } else {
            Write-Result "nvidia-smi in ollama" "FAIL" "GPU not visible in container"
        }
    }
}

Write-Host ""
Write-Host "--- python scripts/compute_detect.py ---"
& $Python (Join-Path $ProjectRoot "scripts\compute_detect.py")

Write-Host ""
Write-Host ("Summary: FAIL=" + $fail + " WARN=" + $warn)
if ($fail -gt 0) {
    Write-Host "See start/Readme.md and infra/docker/Dockerfile.ollama/README.md"
    exit 1
}
Write-Host "Done."
exit 0
