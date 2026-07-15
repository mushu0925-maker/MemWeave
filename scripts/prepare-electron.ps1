param(
  [string]$MirrorBaseUrl = "https://npmmirror.com/mirrors/electron"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$electronDir = Join-Path $root "node_modules\electron"
$packagePath = Join-Path $electronDir "package.json"
$checksumsPath = Join-Path $electronDir "checksums.json"

if (-not (Test-Path -LiteralPath $packagePath)) {
  throw "Missing $packagePath. Run npm install first so the electron package metadata exists."
}
if (-not (Test-Path -LiteralPath $checksumsPath)) {
  throw "Missing $checksumsPath. Cannot verify Electron zip without package checksums."
}

$package = Get-Content -LiteralPath $packagePath -Encoding UTF8 | ConvertFrom-Json
$version = [string]$package.version
$zipName = "electron-v$version-win32-x64.zip"
$checksums = Get-Content -LiteralPath $checksumsPath -Encoding UTF8 | ConvertFrom-Json
$expectedHash = [string]$checksums.$zipName
if (-not $expectedHash) {
  throw "Checksum for $zipName was not found in $checksumsPath."
}

$cacheDir = Join-Path $root ".npm-cache\electron"
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
$zipPath = Join-Path $cacheDir $zipName
$url = "$MirrorBaseUrl/$version/$zipName"

if (-not (Test-Path -LiteralPath $zipPath)) {
  Write-Host "Downloading $url"
  Invoke-WebRequest -Uri $url -OutFile $zipPath
}

$actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
  throw "Electron zip checksum mismatch. expected=$expectedHash actual=$actualHash"
}

$distDir = Join-Path $electronDir "dist"
if (Test-Path -LiteralPath $distDir) {
  Remove-Item -LiteralPath $distDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Expand-Archive -LiteralPath $zipPath -DestinationPath $distDir -Force

$pathTxt = Join-Path $electronDir "path.txt"
[System.IO.File]::WriteAllText($pathTxt, "electron.exe", [System.Text.Encoding]::ASCII)

$electronExe = Join-Path $distDir "electron.exe"
if (-not (Test-Path -LiteralPath $electronExe)) {
  throw "Electron executable was not extracted to $electronExe."
}

Write-Host "Electron prepared: $electronExe"
& $electronExe --version
