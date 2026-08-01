@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
  echo Error: not inside a git repository.
  exit /b 1
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "branch=%%b"
if /i "%branch%" == "HEAD" (
  echo Error: detached HEAD. Switch to a branch before using this script.
  exit /b 1
)

set "remote=origin"
set "message=Update organisation"

echo Repository root: %cd%
echo Current branch: %branch%
echo Remote: %remote%
echo.
echo Choisissez une action :
echo 1) recevoir mise a jour
echo 2) push mise a jour
set /p choice=Entrez 1 ou 2 : 

if "%choice%" == "1" goto pull
if "%choice%" == "2" goto push
echo Choix invalide : %choice%. Utilisez 1 ou 2.
exit /b 1

:pull
echo.
echo == Statut git ==
git status --short
echo.
echo Recuperation des mises a jour depuis %remote%/%branch%...
git fetch %remote%
git pull --ff-only %remote% %branch%
echo Mise a jour recue.
goto end

:push
echo.
echo == Statut git ==
git status --short
echo.
set /p confirm=Commit all changes and push to %remote%/%branch%? [y/N] 
if /i "%confirm%" == "y" goto commit
echo Aborted. No changes were pushed.
exit /b 0

:commit
git add .
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "%message%"
) else (
  echo No staged changes to commit.
)
git push --set-upstream %remote% %branch%
echo Mises a jour envoye.
goto end

:end
endlocal
