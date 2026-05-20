#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#   GOOVA — Script d'installation complète sur VPS Ubuntu 24.04
#   Usage : sudo bash install.sh
# ═══════════════════════════════════════════════════════════════════
set -e

# ── CONFIGURATION ──────────────────────────────────────────────────
APP_DIR="/var/www/goova"
PUBLIC_DIR="/var/www/goova/public"
REPO_URL="https://github.com/abocoum5/Safarway"
VPS_IP="72.61.102.253"
DB_NAME="goova_db"
DB_USER="goova"
SERVICE_USER="goova"

# ── 0. Vérifications ───────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  echo "❌ Exécuter en root : sudo bash install.sh"
  exit 1
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "        INSTALLATION GOOVA — VPS Ubuntu 24.04"
echo "══════════════════════════════════════════════════════════"
echo ""

# ── 1. Variables d'environnement ───────────────────────────────────
echo "📝 Configuration des variables d'environnement :"
echo ""
read -p "  DB_PASSWORD (choisissez un mot de passe fort) : " DB_PASSWORD
read -p "  SECRET_KEY  (chaîne aléatoire longue pour JWT) : " SECRET_KEY
read -p "  VONAGE_API_KEY : " VONAGE_API_KEY
read -p "  VONAGE_API_SECRET : " VONAGE_API_SECRET
read -p "  WHATSAPP_ADMIN_PHONE (ex: 33601821166) : " WHATSAPP_ADMIN_PHONE
read -p "  WHATSAPP_CALLMEBOT_KEY : " WHATSAPP_CALLMEBOT_KEY
read -p "  VAPID_PUBLIC_KEY : " VAPID_PUBLIC_KEY

echo ""
echo "  VAPID_PRIVATE_KEY — collez la clé PEM complète (BEGIN ... END EC PRIVATE KEY),"
echo "  puis appuyez sur CTRL+D sur une nouvelle ligne :"
VAPID_PRIVATE_KEY=$(cat)

echo ""
echo "  ✅ Variables enregistrées."
echo ""

# ── 2. Mise à jour système ─────────────────────────────────────────
echo "🔄 Mise à jour du système..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 3. Installation des paquets ────────────────────────────────────
echo "📦 Installation des paquets requis..."
apt-get install -y -qq \
  python3 python3-pip python3-venv python3-dev \
  postgresql postgresql-contrib \
  nginx \
  git curl wget \
  ufw \
  libpq-dev gcc \
  certbot python3-certbot-nginx

echo "  ✅ Paquets installés"

# ── 4. PostgreSQL ──────────────────────────────────────────────────
echo ""
echo "🐘 Configuration PostgreSQL..."
systemctl enable postgresql --quiet
systemctl start postgresql

# Crée l'utilisateur et la base (ignore si déjà existants)
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true

echo "  ✅ Base '$DB_NAME' prête"

# ── 5. Utilisateur système ─────────────────────────────────────────
echo ""
echo "👤 Création de l'utilisateur système '$SERVICE_USER'..."
id -u $SERVICE_USER &>/dev/null || useradd -r -s /bin/false -d $APP_DIR $SERVICE_USER

# ── 6. Clonage du dépôt ────────────────────────────────────────────
echo ""
echo "📥 Clonage du dépôt GitHub..."
if [ -d "$APP_DIR/.git" ]; then
  echo "  Dépôt existant — git pull..."
  git -C $APP_DIR pull origin main
else
  git clone $REPO_URL $APP_DIR
fi
echo "  ✅ Code source récupéré"

# ── 7. Virtualenv Python ───────────────────────────────────────────
echo ""
echo "🐍 Création de l'environnement Python..."
python3 -m venv $APP_DIR/venv
$APP_DIR/venv/bin/pip install --upgrade pip --quiet
$APP_DIR/venv/bin/pip install -r $APP_DIR/backend/requirements.txt --quiet
echo "  ✅ Dépendances Python installées"

# ── 8. Fichier .env ────────────────────────────────────────────────
echo ""
echo "⚙️  Création du fichier .env..."
cat > $APP_DIR/backend/.env << ENVEOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
SECRET_KEY=$SECRET_KEY
VONAGE_API_KEY=$VONAGE_API_KEY
VONAGE_API_SECRET=$VONAGE_API_SECRET
WHATSAPP_ADMIN_PHONE=$WHATSAPP_ADMIN_PHONE
WHATSAPP_CALLMEBOT_KEY=$WHATSAPP_CALLMEBOT_KEY
VAPID_PUBLIC_KEY=$VAPID_PUBLIC_KEY
VAPID_PRIVATE_KEY=$VAPID_PRIVATE_KEY
ENVEOF
chmod 600 $APP_DIR/backend/.env
echo "  ✅ .env créé (permissions 600)"

# ── 9. Frontend — copie et patch des URLs ─────────────────────────
echo ""
echo "🔧 Déploiement du frontend..."
mkdir -p $PUBLIC_DIR
cp -r $APP_DIR/frontend/. $PUBLIC_DIR/

# Remplace l'URL de l'API Render par le chemin /api (même serveur)
sed -i 's|https://safarway\.onrender\.com|/api|g' $PUBLIC_DIR/index.html
# Remplace l'URL Vercel par l'IP du VPS (pour les liens WhatsApp)
sed -i "s|https://safarway-roan\.vercel\.app|http://$VPS_IP|g" $PUBLIC_DIR/index.html

echo "  ✅ Frontend déployé dans $PUBLIC_DIR"

# ── 10. Systemd service ────────────────────────────────────────────
echo ""
echo "⚡ Configuration du service systemd..."
cp $APP_DIR/deploy/goova.service /etc/systemd/system/goova.service
systemctl daemon-reload
systemctl enable goova --quiet
systemctl restart goova

# Attendre que le service démarre
sleep 3
if systemctl is-active --quiet goova; then
  echo "  ✅ Service goova démarré"
else
  echo "  ⚠️  Problème au démarrage — vérifiez : journalctl -u goova -n 50"
fi

# ── 11. Nginx ──────────────────────────────────────────────────────
echo ""
echo "🌐 Configuration Nginx..."
cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/goova
ln -sf /etc/nginx/sites-available/goova /etc/nginx/sites-enabled/goova
rm -f /etc/nginx/sites-enabled/default

if nginx -t -q 2>/dev/null; then
  systemctl restart nginx
  systemctl enable nginx --quiet
  echo "  ✅ Nginx configuré et démarré"
else
  echo "  ❌ Erreur dans la config Nginx — vérifiez nginx -t"
fi

# ── 12. Firewall UFW ──────────────────────────────────────────────
echo ""
echo "🔒 Configuration du firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
echo "  ✅ Firewall activé (SSH + HTTP/HTTPS)"

# ── 13. Permissions finales ────────────────────────────────────────
chown -R $SERVICE_USER:www-data $APP_DIR
chown -R www-data:www-data $PUBLIC_DIR
chmod -R 755 $PUBLIC_DIR
chmod 600 $APP_DIR/backend/.env

# ── FIN ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  ✅  INSTALLATION TERMINÉE !"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "  🌍 Application : http://$VPS_IP"
echo "  🔌 API docs    : http://$VPS_IP/api/docs"
echo ""
echo "  ── Commandes utiles ─────────────────────────────────"
echo "  Logs backend  : journalctl -u goova -f"
echo "  Statut        : systemctl status goova"
echo "  Mise à jour   : sudo bash $APP_DIR/deploy/update.sh"
echo ""
echo "  ── HTTPS (quand vous avez un domaine) ───────────────"
echo "  certbot --nginx -d votre-domaine.com"
echo "══════════════════════════════════════════════════════════"
