param([string]$msg = "update")
git add -A
git commit -m $msg
git push origin main
