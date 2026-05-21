#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#   GOOVA — Script de mise à jour
#   Usage : sudo bash /var/www/goova/deploy/update.sh
# ═══════════════════════════════════════════════════════════════════
set -e

APP_DIR="/var/www/goova"
PUBLIC_DIR="/var/www/goova/public"
VPS_IP="goova.pro"

if [ "$EUID" -ne 0 ]; then
  echo "❌ Exécuter en root : sudo bash update.sh"
  exit 1
fi

echo ""
echo "🔄 Mise à jour Goova en cours..."
echo ""

# 1. Récupérer le dernier code
echo "  📥 git pull origin main..."
git -C $APP_DIR pull origin main
echo "  ✅ Code mis à jour"

# 2. Mettre à jour les dépendances Python
echo "  🐍 Mise à jour des dépendances Python..."
$APP_DIR/venv/bin/pip install -r $APP_DIR/backend/requirements.txt --quiet
echo "  ✅ Dépendances à jour"

# 3. Redéployer le frontend (patch URLs)
echo "  🔧 Redéploiement du frontend..."
cp -r $APP_DIR/frontend/. $PUBLIC_DIR/
mkdir -p $PUBLIC_DIR/.well-known
cp $APP_DIR/frontend/assetlinks.json $PUBLIC_DIR/.well-known/assetlinks.json
chown -R www-data:www-data $PUBLIC_DIR
chmod -R 755 $PUBLIC_DIR
echo "  ✅ Frontend déployé"

# 4. Redémarrer le backend
echo "  ⚡ Redémarrage du backend..."
systemctl restart goova
sleep 2
if systemctl is-active --quiet goova; then
  echo "  ✅ Backend redémarré"
else
  echo "  ❌ Erreur — logs : journalctl -u goova -n 30"
  exit 1
fi

echo ""
echo "  ✅ Mise à jour terminée !"
echo "  Logs : journalctl -u goova -f"
echo ""
