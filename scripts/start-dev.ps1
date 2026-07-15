param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000,
  [int[]]$FallbackFrontendPorts = @(3001, 3002, 3003),
  [switch]$RestartBackend
)

$ErrorActionPreference = "Stop"

# Some managed Windows shells expose both PATH and Path. Start-Process treats
# them as duplicate dictionary keys, so normalize the process environment first.
$processPath = $env:Path
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $processPath, "Process")

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$logsDir = Join-Path $root "logs"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$nextBin = Join-Path $frontendDir "node_modules\next\dist\bin\next"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

function Test-TcpPort {
  param([int]$Port)

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $asyncResult = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $asyncResult.AsyncWaitHandle.WaitOne(250, $false)) {
      return $false
    }
    $client.EndConnect($asyncResult)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$Seconds = 35
  )

  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 800
    }
  }
  return $false
}

function Test-HttpStatus {
  param(
    [string]$Url,
    [int[]]$AcceptedStatusCodes = @(200)
  )

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
    return $AcceptedStatusCodes -contains [int]$response.StatusCode
  } catch {
    return $false
  }
}

function Test-FrontendReady {
  param([int]$Port)

  try {
    $baseUrl = "http://127.0.0.1:$Port"
    $response = Invoke-WebRequest -UseBasicParsing -Uri $baseUrl -TimeoutSec 4
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 400) {
      return $false
    }

    $assetPaths = [regex]::Matches($response.Content, '/_next/static/[^"''\s<>]+') |
      ForEach-Object { [System.Net.WebUtility]::HtmlDecode($_.Value) } |
      Select-Object -Unique -First 8
    if (-not $assetPaths) {
      return $false
    }

    foreach ($assetPath in $assetPaths) {
      if (-not (Test-HttpStatus -Url "$baseUrl$assetPath")) {
        return $false
      }
    }
    return $true
  } catch {
    return $false
  }
}

function Test-BackendApiCurrent {
  param([int]$Port)

  $rawSourcesOk = Test-HttpStatus -Url "http://127.0.0.1:$Port/api/v1/raw-sources"
  $personaItemsOk = Test-HttpStatus -Url "http://127.0.0.1:$Port/api/v1/persona-items"
  $sourceSegmentsOk = Test-HttpStatus -Url "http://127.0.0.1:$Port/api/v1/source-segments"
  return $rawSourcesOk -and $personaItemsOk -and $sourceSegmentsOk
}

function Get-ListeningProcessId {
  param([int]$Port)

  try {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
    if ($null -ne $connection) {
      return [int]$connection.OwningProcess
    }
  } catch {
    # Fall through to netstat for older shells or restricted environments.
  }

  try {
    $line = netstat -ano -p tcp | Select-String -Pattern "127\.0\.0\.1:$Port\s+0\.0\.0\.0:0\s+LISTENING\s+(\d+)" | Select-Object -First 1
    if ($null -ne $line -and $line.Matches.Count -gt 0) {
      return [int]$line.Matches[0].Groups[1].Value
    }
  } catch {
    return $null
  }

  return $null
}

function Stop-StaleBackendIfSafe {
  param([int]$Port)

  $processId = Get-ListeningProcessId -Port $Port
  if ($null -eq $processId) {
    Write-Warning "Could not identify the process using backend port $Port."
    return $false
  }

  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($null -eq $process) {
    Write-Warning "Could not inspect process $processId on backend port $Port."
    return $false
  }

  $devProcessNames = @("python", "python3", "uvicorn")
  if ($devProcessNames -notcontains $process.ProcessName.ToLowerInvariant()) {
    Write-Warning "Port $Port is owned by $($process.ProcessName) ($processId), so it was not stopped automatically."
    return $false
  }

  Stop-Process -Id $processId -Force
  Write-Host "Stopped stale backend process $($process.ProcessName) ($processId) on port $Port"
  Start-Sleep -Milliseconds 800
  return $true
}

function Find-ReadyFrontendPort {
  param(
    [int[]]$Ports,
    [int]$Seconds = 2
  )

  foreach ($port in $Ports) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
      if (Test-FrontendReady -Port $port) {
        return $port
      }
      Start-Sleep -Milliseconds 500
    }
  }
  return $null
}

function Find-FreePort {
  param([int[]]$Ports)

  foreach ($port in $Ports) {
    if (-not (Test-TcpPort -Port $port)) {
      return $port
    }
  }
  return $null
}

if (-not (Test-Path $nextBin)) {
  throw "Missing Next.js binary: $nextBin. Run npm install in frontend first."
}

if (Test-Path $venvPython) {
  $pythonExe = $venvPython
} else {
  $pythonCommand = Get-Command python -ErrorAction Stop
  $pythonExe = $pythonCommand.Source
}

& $pythonExe -c "import fastapi, pydantic, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "Backend dependencies are missing for $pythonExe. Run npm run setup first."
}

$nodeCommand = Get-Command node -ErrorAction Stop
$nodeExe = $nodeCommand.Source

$backendUrl = "http://127.0.0.1:$BackendPort/health"
$backendOk = Wait-HttpOk -Url $backendUrl -Seconds 2
$backendApiCurrent = $false
if ($backendOk) {
  $backendApiCurrent = Test-BackendApiCurrent -Port $BackendPort
}

if ($RestartBackend -and (Test-TcpPort -Port $BackendPort)) {
  Write-Host "RestartBackend requested. Restarting backend if it is a Python dev process."
  Stop-StaleBackendIfSafe -Port $BackendPort | Out-Null
  $backendOk = $false
  $backendApiCurrent = $false
}

if ($backendOk -and $backendApiCurrent) {
  Write-Host "Backend already ready on http://127.0.0.1:$BackendPort"
} else {
  if ($backendOk -and -not $backendApiCurrent) {
    Write-Warning "Backend on port $BackendPort is stale or from the old API shape. Restarting it if it is a Python dev process."
    Stop-StaleBackendIfSafe -Port $BackendPort | Out-Null
  }

  if (Test-TcpPort -Port $BackendPort) {
    Write-Warning "Backend port $BackendPort is occupied, but the current architecture API is not ready."
  } else {
    $backendLog = Join-Path $logsDir "backend-dev.out.log"
    $backendErrLog = Join-Path $logsDir "backend-dev.err.log"
    Start-Process -WindowStyle Hidden -FilePath $pythonExe -ArgumentList @(
      "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $BackendPort
    ) -WorkingDirectory $backendDir -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrLog | Out-Null
    Write-Host "Started backend on http://127.0.0.1:$BackendPort"
  }
}

$frontendPorts = @($FrontendPort) + $FallbackFrontendPorts | Select-Object -Unique
$readyFrontendPort = Find-ReadyFrontendPort -Ports $frontendPorts -Seconds 2

if ($null -ne $readyFrontendPort) {
  Write-Host "Frontend already ready on http://127.0.0.1:$readyFrontendPort"
} else {
  $frontendLaunchPort = $null
  if (-not (Test-TcpPort -Port $FrontendPort)) {
    $frontendLaunchPort = $FrontendPort
  } else {
    Write-Warning "Frontend port $FrontendPort is occupied, but HTTP did not respond."
    $frontendLaunchPort = Find-FreePort -Ports $FallbackFrontendPorts
  }

  if ($null -eq $frontendLaunchPort) {
    Write-Warning "No free frontend port found in: $($frontendPorts -join ', ')"
  } else {
    $frontendLog = Join-Path $logsDir "frontend-dev.out.log"
    $frontendErrLog = Join-Path $logsDir "frontend-dev.err.log"
    Start-Process -WindowStyle Hidden -FilePath $nodeExe -ArgumentList @(
      $nextBin, "dev", "--hostname", "127.0.0.1", "--port", $frontendLaunchPort
    ) -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrLog | Out-Null
    Write-Host "Started frontend on http://127.0.0.1:$frontendLaunchPort"
    $readyFrontendPort = $frontendLaunchPort
  }
}

$backendOk = (Wait-HttpOk -Url $backendUrl) -and (Test-BackendApiCurrent -Port $BackendPort)
if ($null -ne $readyFrontendPort) {
  $frontendDeadline = (Get-Date).AddSeconds(45)
  $frontendOk = $false
  while ((Get-Date) -lt $frontendDeadline -and -not $frontendOk) {
    $frontendOk = Test-FrontendReady -Port $readyFrontendPort
    if (-not $frontendOk) {
      Start-Sleep -Milliseconds 800
    }
  }
} else {
  $frontendOk = $false
}

Write-Host ""
Write-Host "Dev server status:"
Write-Host "  Backend:  $(if ($backendOk) { 'ready' } else { 'not ready, check logs/backend-dev.*.log' })"
Write-Host "  Frontend: $(if ($frontendOk) { "ready on port $readyFrontendPort" } else { 'not ready, check logs/frontend-dev.*.log' })"
Write-Host ""
Write-Host "Open:"
if ($frontendOk) {
  Write-Host "  http://127.0.0.1:$readyFrontendPort"
}
if ($backendOk) {
  Write-Host "  http://127.0.0.1:$BackendPort/docs"
}

if (-not ($backendOk -and $frontendOk)) {
  exit 1
}
