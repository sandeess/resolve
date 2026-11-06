#!/usr/bin/env bash
# Creates a sign-in account in Keycloak (realm "resolve") with a temporary password.
# The person must choose their own password at first sign-in.
#
#   cd /opt/resolve && sudo bash deploy/add-user.sh someone@example.com
#   cd /opt/resolve && sudo bash deploy/add-user.sh boss@example.com --admin
#
# Then add their email to a journal on the People page in the app. That can be done
# before they ever sign in: they get access the first time they do.
set -euo pipefail
cd "$(dirname "$0")/.."

EMAIL="${1:-}"
ROLE="${2:-}"
[[ "$EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || {
  echo "Usage: bash deploy/add-user.sh someone@example.com [--admin]"; exit 1; }
[ -z "$ROLE" ] || [ "$ROLE" = "--admin" ] || { echo "Unknown option: $ROLE"; exit 1; }

ENV_FILE="${ENV_FILE:-.env.prod}"
COMPOSE="${COMPOSE:-docker compose --env-file $ENV_FILE -f compose.prod.yml}"
ADMIN_PASSWORD="$(grep -E '^KEYCLOAK_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$ADMIN_PASSWORD" ] || { echo "KEYCLOAK_ADMIN_PASSWORD not found in $ENV_FILE"; exit 1; }

KC="$COMPOSE exec -T keycloak /opt/keycloak/bin/kcadm.sh"
$KC config credentials --server http://localhost:8080 --realm master \
  --user admin --password "$ADMIN_PASSWORD" >/dev/null

if [ -n "$($KC get users -r resolve -q "email=$EMAIL" -q exact=true --fields id --format csv --noquotes | tr -d '\r')" ]; then
  echo "A user with $EMAIL already exists. To reset their password in Keycloak, use set-password."
  exit 1
fi

PASSWORD="$(openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | cut -c1-16)"
$KC create users -r resolve \
  -s username="$EMAIL" -s email="$EMAIL" -s emailVerified=true -s enabled=true \
  -s 'requiredActions=["UPDATE_PASSWORD"]' >/dev/null
$KC set-password -r resolve --username "$EMAIL" --new-password "$PASSWORD" --temporary
if [ "$ROLE" = "--admin" ]; then
  $KC add-roles -r resolve --uusername "$EMAIL" --rolename resolve-admin
fi

DOMAIN="$(grep -E '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
cat <<EOF

Account created.

    Sign in at:  https://app.${DOMAIN}
    Email:       $EMAIL
    Temporary password (they must change it at first sign-in):

        $PASSWORD

Next: add $EMAIL to a journal on the People page, then send them these details
through a private channel (not a public chat or a shared document).
EOF
