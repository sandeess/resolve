#!/usr/bin/env bash
# One-command setup of Resolve on a fresh Ubuntu 22.04/24.04 VPS (any provider).
# It installs Docker, a firewall and swap, writes .env.prod with generated secrets,
# builds the production realm, and starts the stack. Read it before you run it.
#
#   git clone https://github.com/sandeess/resolve.git /opt/resolve
#   cd /opt/resolve && sudo bash deploy/bootstrap-vps.sh
#
# Before running: create three DNS A records (app, auth, mcp) for your domain that
# point at this server, DNS only (no proxy), so Let's Encrypt can issue certificates.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo bash deploy/bootstrap-vps.sh"; exit 1; }
cd "$(dirname "$0")/.."

ask() { # ask VAR "Prompt" [default]
  local var="$1" prompt="$2" def="${3:-}" reply
  read -r -p "$prompt${def:+ [$def]}: " reply
  printf -v "$var" '%s' "${reply:-$def}"
}
secret() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-32; }

if [ -f .env.prod ]; then
  echo ".env.prod already exists; not overwriting it. Delete it to start over."
  exit 1
fi

echo "== Resolve production setup =="
ask DOMAIN "Your domain (Resolve will live at app./auth./mcp. of it)" "sortitouthq.com"
ask ACME_EMAIL "Email for Let's Encrypt notices"
ask ADMIN_EMAIL "Email of the first Resolve administrator (you)" "$ACME_EMAIL"
read -r -s -p "DeepInfra API key (input hidden): " DEEPINFRA_API_KEY; echo
ask ACCESS_URL "Google Form link for access requests (optional, Enter to skip)" ""
[ -n "$DEEPINFRA_API_KEY" ] || { echo "A DeepInfra API key is required."; exit 1; }

echo "== Checking DNS =="
IP="$(curl -fsS https://api.ipify.org || true)"
for host in app auth mcp; do
  resolved="$(getent hosts "$host.$DOMAIN" | awk '{print $1}' | head -1 || true)"
  if [ -n "$IP" ] && [ "$resolved" != "$IP" ]; then
    echo "WARNING: $host.$DOMAIN resolves to '${resolved:-nothing}', this server is $IP."
    echo "         Certificates will fail until the A record points here (DNS only, no proxy)."
  fi
done

echo "== Installing Docker, firewall, swap =="
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
apt-get install -y -qq ufw python3 openssl >/dev/null
ufw allow OpenSSH >/dev/null && ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== Writing .env.prod (secrets generated here, readable by root only) =="
ADMIN_PASSWORD="$(secret)"
umask 077
cat > .env.prod <<EOF
DOMAIN=$DOMAIN
ACME_EMAIL=$ACME_EMAIL
POSTGRES_PASSWORD=$(secret)
KEYCLOAK_ADMIN_PASSWORD=$(secret)
RESOLVE_ADMIN_EMAIL=$ADMIN_EMAIL
RESOLVE_ADMIN_INITIAL_PASSWORD=$ADMIN_PASSWORD
DEEPINFRA_API_KEY=$DEEPINFRA_API_KEY
LITELLM_MASTER_KEY=$(secret)
MAX_UPLOAD_MB=50
ACCESS_REQUEST_URL=$ACCESS_URL
EOF
chmod 600 .env.prod

echo "== Building the production realm and starting the stack (several minutes) =="
python3 deploy/keycloak/make_prod_realm.py --domain "$DOMAIN"
docker compose --env-file .env.prod -f compose.prod.yml up -d --build

cat <<EOF

Started. Give it a minute or two for Keycloak and the certificates, then open:

    https://app.$DOMAIN

Sign in as:   $ADMIN_EMAIL
Temporary password (you must change it at first sign-in):

    $ADMIN_PASSWORD

It is also in /opt/resolve/.env.prod (root only). Check progress with:

    docker compose --env-file .env.prod -f compose.prod.yml ps
    docker compose --env-file .env.prod -f compose.prod.yml logs -f proxy backend

Next: create a journal, add people on the People page, and set up backups
(deploy/PRODUCTION.md, "Operations").
EOF
