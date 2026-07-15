param(
  [switch]$SkipDesktop
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
$setupTemp = Join-Path $root ".setup-tmp"

function Invoke-Checked {
  param(
    [string]$Command,
    [string[]]$Arguments
  )

  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

$pythonCommand = Get-Command python -ErrorAction Stop
New-Item -ItemType Directory -Force -Path $setupTemp | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$env:TEMP = $setupTemp
$env:TMP = $setupTemp

try {
  if (-not (Test-Path -LiteralPath $venvPython)) {
    Invoke-Checked -Command $pythonCommand.Source -Arguments @("-m", "venv", "--without-pip", $venvDir)
  }
  if (-not (Test-Path -LiteralPath $venvPip)) {
    Invoke-Checked -Command $pythonCommand.Source -Arguments @("-m", "pip", "--python", $venvDir, "install", "pip")
  }
  Invoke-Checked -Command $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $backendDir "requirements.txt"))

  Push-Location $frontendDir
  try {
    Invoke-Checked -Command "npm" -Arguments @("ci")
  } finally {
    Pop-Location
  }

  if (-not $SkipDesktop) {
    Push-Location $root
    try {
      Invoke-Checked -Command "npm" -Arguments @("ci", "--ignore-scripts")
      Invoke-Checked -Command "powershell" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $root "scripts\prepare-electron.ps1")
      )
    } finally {
      Pop-Location
    }
  }

  $backendEnv = Join-Path $backendDir ".env"
  if (-not (Test-Path -LiteralPath $backendEnv)) {
    Copy-Item -LiteralPath (Join-Path $backendDir ".env.example") -Destination $backendEnv
  }

  $frontendEnv = Join-Path $frontendDir ".env.local"
  if (-not (Test-Path -LiteralPath $frontendEnv)) {
    Copy-Item -LiteralPath (Join-Path $frontendDir ".env.local.example") -Destination $frontendEnv
  }

  Write-Host "MemWeave development dependencies are ready."
  Write-Host "Run: npm run dev"
} finally {
  $env:TEMP = $previousTemp
  $env:TMP = $previousTmp
  Remove-Item -LiteralPath $setupTemp -Recurse -Force -ErrorAction SilentlyContinue
}
