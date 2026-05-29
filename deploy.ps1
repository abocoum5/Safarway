Write-Host "🚀 Deploiement en production..." -ForegroundColor Cyan
git checkout main
git merge develop
git push origin main
git checkout develop
Write-Host "✅ Production mise a jour ! Retour sur develop." -ForegroundColor Green
