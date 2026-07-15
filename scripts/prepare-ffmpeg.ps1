param(
  [string]$Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
  [string]$ExpectedSha256 = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$cacheDir = Join-Path $root ".npm-cache\ffmpeg"
$extractDir = Join-Path $cacheDir "extract"
$zipFileName = [System.IO.Path]::GetFileName(([Uri]$Url).AbsolutePath)
if (-not $zipFileName) {
  $zipFileName = "ffmpeg.zip"
}
$zipPath = Join-Path $cacheDir $zipFileName
$targetDir = Join-Path $root "tools\ffmpeg"
$targetExe = Join-Path $targetDir "ffmpeg.exe"

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-ZipArchive {
  param([string]$Path)

  try {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    $archive.Dispose()
    return $true
  } catch {
    return $false
  }
}

if (Test-Path -LiteralPath $zipPath) {
  $existingZip = Get-Item -LiteralPath $zipPath
  if ($existingZip.Length -lt 1048576 -or -not (Test-ZipArchive -Path $zipPath)) {
    Remove-Item -LiteralPath $zipPath -Force
  }
}

if (-not (Test-Path -LiteralPath $zipPath)) {
  Write-Host "Downloading $Url"
  $downloadPath = "$zipPath.download"
  Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if ($curl) {
    & $curl.Source -L --fail --retry 3 --connect-timeout 30 -o $downloadPath $Url
    if ($LASTEXITCODE -ne 0) {
      Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
      throw "curl.exe failed with exit code $LASTEXITCODE while downloading $Url"
    }
  } else {
    Invoke-WebRequest -Uri $Url -OutFile $downloadPath
  }
  Move-Item -LiteralPath $downloadPath -Destination $zipPath -Force
}

if ((Get-Item -LiteralPath $zipPath).Length -eq 0) {
  throw "Downloaded ffmpeg zip is empty: $zipPath"
}

if (-not (Test-ZipArchive -Path $zipPath)) {
  Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
  throw "Downloaded ffmpeg zip is incomplete or invalid and was removed: $zipPath"
}

$actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "ffmpeg zip SHA256: $actualHash"
if ($ExpectedSha256 -and $actualHash -ne $ExpectedSha256.ToLowerInvariant()) {
  throw "ffmpeg zip checksum mismatch. expected=$ExpectedSha256 actual=$actualHash"
}

if (Test-Path -LiteralPath $extractDir) {
  Remove-Item -LiteralPath $extractDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

$candidate = Get-ChildItem -LiteralPath $extractDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if (-not $candidate) {
  throw "ffmpeg.exe was not found after extracting $zipPath."
}

Copy-Item -LiteralPath $candidate.FullName -Destination $targetExe -Force

Write-Host "ffmpeg prepared: $targetExe"
& $targetExe -version
