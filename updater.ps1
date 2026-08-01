param(
    [string]$Remote = 'origin',
    [string]$Message = 'Update organisation'
)

Set-StrictMode -Version Latest

$scriptPath = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
Set-Location $scriptPath

if (-not (git rev-parse --git-dir 2>$null)) {
    Write-Error 'Error: not inside a git repository.'
    exit 1
}

$branch = git rev-parse --abbrev-ref HEAD 2>$null | Out-String | Trim()
if ($branch -eq 'HEAD') {
    Write-Error 'Error: detached HEAD. Switch to a branch before using this script.'
    exit 1
}

Write-Host "Repository root: $(Get-Location)"
Write-Host "Current branch: $branch"
Write-Host "Remote: $Remote"
Write-Host ''

Write-Host 'Choisissez une action :'
Write-Host '1) recevoir mise a jour'
Write-Host '2) push mise a jour'
$choice = Read-Host 'Entrez 1 ou 2'

function Show-GitStatus {
    Write-Host ''
    Write-Host '== Statut git =='
    git status --short
    Write-Host ''
}

switch ($choice) {
    '1' {
        Show-GitStatus
        Write-Host "Récupération des mises à jour depuis $Remote/$branch..."
        git fetch $Remote
        git pull --ff-only $Remote $branch
        Write-Host 'Mise à jour reçue.'
    }
    '2' {
        Show-GitStatus
        $confirm = Read-Host "Commit all changes and push to $Remote/$branch? [y/N]"
        if ($confirm -notin 'y', 'Y') {
            Write-Host 'Aborted. No changes were pushed.'
            exit 0
        }
        git add .
        $diff = git diff --cached --quiet
        if ($LASTEXITCODE -ne 0) {
            git commit -m "$Message"
        } else {
            Write-Host 'No staged changes to commit.'
        }
        git push --set-upstream $Remote $branch
        Write-Host 'Mises à jour envoyées.'
    }
    default {
        Write-Error "Choix invalide : $choice. Utilisez 1 ou 2."
        exit 1
    }
}
