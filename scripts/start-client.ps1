param(
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$processPath = $env:Path
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $processPath, "Process")

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$logsDir = Join-Path $root "logs"
$launcherLog = Join-Path $logsDir "client-launcher.log"
$electronDir = Join-Path $root "node_modules\electron"
$electronExe = Join-Path $electronDir "dist\electron.exe"
$electronCli = Join-Path $electronDir "cli.js"
$prepareElectron = Join-Path $root "scripts\prepare-electron.ps1"
$frontendNext = Join-Path $root "frontend\node_modules\next\dist\bin\next"
$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

function Write-LauncherLog {
  param([string]$Message)
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $launcherLog -Encoding UTF8 -Value ("[{0}] {1}" -f $stamp, $Message)
}

function Stop-WithMessage {
  param([string]$Message)
  Write-LauncherLog ("ERROR {0}" -f $Message)
  Write-Host ""
  Write-Host "Client startup failed" -ForegroundColor Red
  Write-Host $Message
  Write-Host ""
  Write-Host ("Log: {0}" -f $launcherLog)
  exit 1
}

function Require-ExistingPath {
  param(
    [string]$RequiredPath,
    [string]$Message
  )
  if (-not (Test-Path -LiteralPath $RequiredPath)) {
    Stop-WithMessage $Message
  }
}

Write-LauncherLog ("Launcher started. root={0} checkOnly={1}" -f $root, $CheckOnly)

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
  Stop-WithMessage "node.exe was not found. Install Node.js or add it to PATH."
}

$env:DESKTOP_NODE_PATH = $nodeCommand.Source
Write-LauncherLog ("Using node={0}" -f $nodeCommand.Source)

if (Test-Path -LiteralPath $venvPython) {
  $pythonExe = $venvPython
} else {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $pythonCommand) {
    Stop-WithMessage "python.exe was not found. Install Python 3.11+ or run npm run setup."
  }
  $pythonExe = $pythonCommand.Source
}

& $pythonExe -c "import fastapi, pydantic, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
  Stop-WithMessage ("Backend dependencies are missing for {0}. Run npm run setup first." -f $pythonExe)
}
$env:DESKTOP_PYTHON_PATH = $pythonExe
Write-LauncherLog ("Using python={0}" -f $pythonExe)

Require-ExistingPath -RequiredPath $frontendNext -Message ("Missing frontend Next.js dependency: {0}. Run npm install in frontend first." -f $frontendNext)
Require-ExistingPath -RequiredPath $electronCli -Message ("Missing Electron npm package: {0}. Run npm install in the project root first." -f $electronCli)

if (-not (Test-Path -LiteralPath $electronExe)) {
  if (-not (Test-Path -LiteralPath $prepareElectron)) {
    Stop-WithMessage ("Missing Electron executable: {0}. Prepare script was not found: {1}." -f $electronExe, $prepareElectron)
  }

  Write-Host "Electron executable is missing. Preparing local Electron..."
  Write-LauncherLog "Electron executable missing. Running prepare-electron."
  & powershell -NoProfile -ExecutionPolicy Bypass -File $prepareElectron
}

Require-ExistingPath -RequiredPath $electronExe -Message ("Electron preparation failed. Still missing: {0}." -f $electronExe)

if ($CheckOnly) {
  Write-Host "Client launcher check passed."
  Write-Host ("Electron: {0}" -f $electronExe)
  Write-Host ("Node: {0}" -f $nodeCommand.Source)
  Write-Host ("Python: {0}" -f $pythonExe)
  Write-Host ("Log: {0}" -f $launcherLog)
  Write-LauncherLog "CheckOnly passed."
  exit 0
}

Set-Location $root
Write-Host "Starting client..."
Write-LauncherLog "Starting Electron client."
$clientProcess = Start-Process -FilePath $electronExe -ArgumentList @($root) -WorkingDirectory $root -PassThru
Write-LauncherLog ("Electron process started. pid={0}" -f $clientProcess.Id)
Write-Host ("Client started. Log: {0}" -f $launcherLog)
