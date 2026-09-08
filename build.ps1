$ErrorActionPreference = "Stop"

$legendaryVersion = "0.21.0"
$legendaryHash = "4C01A14C0ACB0C46069B197AE7212EA4EA6B861661126CA0593CDAC31658FB01"
$legendaryUrl = "https://github.com/legendary-gl/legendary/releases/download/$legendaryVersion/legendary_windows_x64.exe"
$authVersion = "0.20.34"
$authHash = "01EA22EA51749F46A0019657F64FC0D34429FB7CBF9B590C0848C0E0BD9C1F07"
$authUrl = "https://github.com/legendary-gl/legendary/releases/download/$authVersion/legendary.exe"
$vendorDir = Join-Path $PSScriptRoot "vendor"
$legendary = Join-Path $vendorDir "legendary.exe"
$legendaryAuth = Join-Path $vendorDir "legendary-auth.exe"
$icon = Join-Path $PSScriptRoot "icon.ico"

if (-not (Test-Path -LiteralPath $icon)) {
    throw "icon.ico is missing."
}

function Install-VerifiedBinary {
    param(
        [string]$Name,
        [string]$Version,
        [string]$Url,
        [string]$ExpectedHash,
        [string]$Destination
    )

    if ((Test-Path -LiteralPath $Destination) -and
        (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -eq $ExpectedHash) {
        return
    }

    New-Item -ItemType Directory -Path $vendorDir -Force | Out-Null
    Write-Host "Downloading $Name $Version..."
    $temporaryFile = "$Destination.download"
    Invoke-WebRequest -Uri $Url -OutFile $temporaryFile

    $downloadedHash = (Get-FileHash -LiteralPath $temporaryFile -Algorithm SHA256).Hash
    if ($downloadedHash -ne $ExpectedHash) {
        Remove-Item -LiteralPath $temporaryFile -Force
        throw "$Name checksum mismatch. Downloaded file was deleted."
    }

    Move-Item -LiteralPath $temporaryFile -Destination $Destination -Force
}

Install-VerifiedBinary "Legendary" $legendaryVersion $legendaryUrl $legendaryHash $legendary
Install-VerifiedBinary "Legendary sign-in component" $authVersion $authUrl $authHash $legendaryAuth

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python was not found. Install Python 3 with Tkinter and pip."
}

$pythonArgs = @()
if ($python.Name -eq "py.exe") {
    $pythonArgs = @("-3")
}

& $python.Source @pythonArgs -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Installing build requirements failed with exit code $LASTEXITCODE."
}

$version = (& $python.Source @pythonArgs -c "from better_together import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Could not determine the application version."
}

& $python.Source @pythonArgs -m PyInstaller --noconfirm --clean --onefile --windowed `
    --add-binary "$legendary;." `
    --add-binary "$legendaryAuth;." `
    --add-data "$icon;." `
    --icon "$icon" `
    --version-file (Join-Path $PSScriptRoot "version_info.txt") `
    --name "Better Together - Dead By Daylight Launcher" main.py

if ($LASTEXITCODE -ne 0) {
    throw "Building the launcher failed with exit code $LASTEXITCODE."
}

$workspaceRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
Get-ChildItem -LiteralPath $workspaceRoot -Directory -Filter "__pycache__" -Recurse |
    ForEach-Object {
        $cachePath = (Resolve-Path -LiteralPath $_.FullName).Path
        if (-not $cachePath.StartsWith($workspaceRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove cache outside the project: $cachePath"
        }
        Remove-Item -LiteralPath $cachePath -Recurse -Force
    }

$ruffCache = Join-Path $workspaceRoot ".ruff_cache"
if (Test-Path -LiteralPath $ruffCache) {
    $resolvedRuffCache = (Resolve-Path -LiteralPath $ruffCache).Path
    if (-not $resolvedRuffCache.StartsWith($workspaceRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove cache outside the project: $resolvedRuffCache"
    }
    Remove-Item -LiteralPath $resolvedRuffCache -Recurse -Force
}

$buildDir = Join-Path $PSScriptRoot "build"
$specFile = Join-Path $PSScriptRoot "Better Together - Dead By Daylight Launcher.spec"
if (Test-Path -LiteralPath $buildDir) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (Test-Path -LiteralPath $specFile) {
    Remove-Item -LiteralPath $specFile -Force
}

$distDir = Join-Path $PSScriptRoot "dist"
$executable = Join-Path $distDir "Better Together - Dead By Daylight Launcher.exe"
$checksums = Join-Path $distDir "SHA256SUMS.txt"
$hash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash
Set-Content -LiteralPath $checksums `
    -Value "$hash  $([IO.Path]::GetFileName($executable))" `
    -Encoding utf8

Write-Host ""
Write-Host "Built Better Together $version"
Write-Host "Executable: $executable"
Write-Host "Checksums:  $checksums"
