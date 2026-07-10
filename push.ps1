# push.ps1 - quick update for GitHub Pages
# Usage:
#   .\push.ps1                 # commit & push with default message
#   .\push.ps1 "your message"  # commit & push with a custom message
param(
    [string]$Message = "Update"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Ensure gh/git are on PATH (GitHub CLI may not be in the current session)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

git add -A

# Nothing changed -> skip
if (-not (git status --porcelain)) {
    Write-Host "No changes to push." -ForegroundColor Yellow
    return
}

git commit -m $Message
git push

Write-Host ""
Write-Host "Done. Live in ~1-2 min:" -ForegroundColor Green
Write-Host "https://rex0988476.github.io/taiko_filter/" -ForegroundColor Cyan
