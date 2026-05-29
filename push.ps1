param([string]$msg = "update")
git add -A
git commit -m $msg
git push origin develop
Write-Host "✅ Pousse vers develop (staging). Utilise .\deploy.ps1 pour mettre en production." -ForegroundColor Yellow
