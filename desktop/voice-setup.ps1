param(
  [Parameter(Mandatory = $true)]
  [string]$VoiceRoot,
  [Parameter(Mandatory = $true)]
  [string]$ConfigDir
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedNative {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Description,
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$Arguments = @()
  )

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Description failed with exit code $LASTEXITCODE."
  }
}

$upstreamUrl = "https://github.com/index-tts/index-tts.git"
$repoDir = Join-Path $VoiceRoot "index-tts"
$venvPython = Join-Path $repoDir ".venv\Scripts\python.exe"
$modelDir = Read-Host "Enter the existing IndexTTS2 model directory (this helper never downloads model weights)"

if (-not (Test-Path -LiteralPath $modelDir)) {
  throw "The selected model directory does not exist: $modelDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $modelDir "config.yaml"))) {
  throw "The selected model directory must contain config.yaml."
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $git) {
  throw "Git is required to obtain the upstream IndexTTS2 source."
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw "Python is required to create the IndexTTS2 environment."
}

New-Item -ItemType Directory -Force -Path $VoiceRoot | Out-Null
if (-not (Test-Path -LiteralPath $repoDir)) {
  Invoke-CheckedNative -Description "IndexTTS2 source download" -FilePath $git.Source -Arguments @("clone", $upstreamUrl, $repoDir)
}
if (-not (Test-Path -LiteralPath $venvPython)) {
  Invoke-CheckedNative -Description "IndexTTS2 virtual environment creation" -FilePath $python.Source -Arguments @("-m", "venv", (Join-Path $repoDir ".venv"))
}
Invoke-CheckedNative -Description "IndexTTS2 pip upgrade" -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedNative -Description "IndexTTS2 dependency installation" -FilePath $venvPython -Arguments @("-m", "pip", "install", "-e", $repoDir)

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($null -eq $ffmpeg) {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($null -ne $winget) {
    $installFfmpeg = Read-Host "FFmpeg is missing. Install it with winget now? (y/N)"
    if ($installFfmpeg -match "^(y|yes)$") {
      Invoke-CheckedNative -Description "FFmpeg installation" -FilePath $winget.Source -Arguments @("install", "--id", "Gyan.FFmpeg", "--exact", "--accept-source-agreements", "--accept-package-agreements")
    }
  } else {
    Write-Warning "FFmpeg is not installed. Video reference extraction will remain unavailable."
  }
}

$gpu = "cpu"
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($null -ne $nvidiaSmi) {
  $gpu = "cuda"
}

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$envFile = Join-Path $ConfigDir ".env"
$lines = @()
if (Test-Path -LiteralPath $envFile) {
  $lines = Get-Content -LiteralPath $envFile -Encoding UTF8 | Where-Object { $_ -notmatch "^(VOICE_GENERATION_BASE_URL|VOICE_REFERENCE_DIR|VOICE_OUTPUT_DIR|INDEXTTS2_MODEL_DIR|INDEXTTS2_DEVICE)=" }
}
$lines += "VOICE_GENERATION_BASE_URL=http://127.0.0.1:7861"
$lines += ("VOICE_REFERENCE_DIR=" + (Join-Path $ConfigDir "voice_references"))
$lines += ("VOICE_OUTPUT_DIR=" + (Join-Path $ConfigDir "voice_outputs"))
$lines += ("INDEXTTS2_MODEL_DIR=" + $modelDir)
$lines += ("INDEXTTS2_DEVICE=" + $gpu)
[System.IO.File]::WriteAllLines($envFile, $lines, [System.Text.UTF8Encoding]::new($false))

Write-Host "Local voice prerequisites were prepared. Model weights were not downloaded or copied."
Write-Host "Restart MemWeave after providing the local adapter server.py expected by the authorized voice guide."
