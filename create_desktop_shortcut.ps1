$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $ProjectRoot "dist\SmartTrade"
$ExePath = Join-Path $AppDir "SmartTrade.exe"

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "SmartTrade.exe was not found at $ExePath. Run .\build_windows.ps1 first."
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "SmartTrade.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.Description = "SmartTrade Market Scanner"
$Shortcut.IconLocation = "$ExePath,0"
$Shortcut.Save()

Write-Host "Desktop shortcut created:" -ForegroundColor Green
Write-Host $ShortcutPath
