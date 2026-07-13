param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SpecPath = Join-Path $ProjectRoot "SmartTrade.spec"
$BuildPath = Join-Path $ProjectRoot "build"
$DistPath = Join-Path $ProjectRoot "dist"
$ExePath = Join-Path $ProjectRoot "dist\SmartTrade\SmartTrade.exe"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Remove-BuildFolder($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $Resolved = (Resolve-Path -LiteralPath $Path).Path

    if (-not $Resolved.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside project: $Resolved"
    }

    if (-not $Clean) {
        $Answer = Read-Host "Remove old folder '$Resolved'? Type YES to continue"
        if ($Answer -ne "YES") {
            throw "Build cancelled. Old folder was not removed: $Resolved"
        }
    }

    Remove-Item -LiteralPath $Resolved -Recurse -Force
}

function Invoke-Checked($Command, $Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

Write-Step "Checking PyInstaller"
Invoke-Checked "python" @("-c", "import PyInstaller, sys; print('PyInstaller', PyInstaller.__version__)")

if (-not (Test-Path -LiteralPath $SpecPath)) {
    throw "Missing SmartTrade.spec at $SpecPath"
}

Write-Step "Cleaning previous build output"
Remove-BuildFolder $BuildPath
Remove-BuildFolder $DistPath

Write-Step "Building SmartTrade.exe in onedir mode"
Push-Location $ProjectRoot
try {
    Invoke-Checked "python" @("-m", "PyInstaller", "--noconfirm", $SpecPath)
}
finally {
    Pop-Location
}

Write-Step "Verifying build output"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Build failed: SmartTrade.exe was not created at $ExePath"
}

Write-Host ""
Write-Host "SmartTrade Windows build completed successfully." -ForegroundColor Green
Write-Host "EXE: $ExePath"
Write-Host "Run it with:"
Write-Host ".\dist\SmartTrade\SmartTrade.exe"
