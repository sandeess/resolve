#!/usr/bin/env bash
# Backs up everything Resolve cannot rebuild: the app database, Keycloak's database
# (users and sign-in settings) and the uploaded files. Keeps the last KEEP_DAYS days.
#
#   cd /opt/resolve && sudo bash deploy/backup.sh
#
# Nightly (03:17), as root:
#   echo '17 3 * * * root cd /opt/resolve && bash deploy/backup.sh >> /var/log/resolve-backup.log 2>&1' \
#     | sudo tee /etc/cron.d/resolve-backup
#
# Copy /var/backups/resolve off the server too (another machine or object storage):
# a backup on the same disk does not survive losing the server.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="${COMPOSE:-docker compose --env-file .env.prod -f compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/resolve}"
KEEP_DAYS="${KEEP_DAYS:-14}"
VOLUME="${VOLUME:-$(basename "$PWD" | tr 'A-Z' 'a-z')_app-files}"
STAMP="$(date +%F_%H%M)"

umask 077
mkdir -p "$BACKUP_DIR"

echo "== $(date -Is) backing up to $BACKUP_DIR"
for database in app keycloak; do
  $COMPOSE exec -T db pg_dump -U postgres --no-owner "$database" | gzip > "$BACKUP_DIR/$database-$STAMP.sql.gz"
  echo "  database $database: $(du -h "$BACKUP_DIR/$database-$STAMP.sql.gz" | cut -f1)"
done

docker run --rm -v "$VOLUME":/data:ro -v "$BACKUP_DIR":/out alpine \
  tar czf "/out/files-$STAMP.tgz" -C /data .
echo "  uploaded files: $(du -h "$BACKUP_DIR/files-$STAMP.tgz" | cut -f1)"

# A dump that is empty or truncated is worse than none: fail loudly.
for file in "$BACKUP_DIR"/app-$STAMP.sql.gz "$BACKUP_DIR"/keycloak-$STAMP.sql.gz; do
  gzip -t "$file"
  [ "$(zcat "$file" | wc -c)" -gt 1000 ] || { echo "ERROR: $file looks empty"; exit 1; }
done
tar --force-local -tzf "$BACKUP_DIR/files-$STAMP.tgz" >/dev/null

find "$BACKUP_DIR" -type f \( -name '*.sql.gz' -o -name '*.tgz' \) -mtime +"$KEEP_DAYS" -delete
echo "== done; backups older than $KEEP_DAYS days removed"
