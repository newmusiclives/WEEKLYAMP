#!/bin/sh
# Nightly Postgres backup on the server, keeps 14 days. Installed by README step 1 as /etc/cron.d/dispatch-backup.
set -eu
cd /opt/dispatch/app/ops/hetzner
OUT=/opt/dispatch/backups/nightly-$(date +%Y%m%d).dump
docker compose -p dispatch exec -T db sh -c 'pg_dump -Fc -U $POSTGRES_USER $POSTGRES_DB' > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
find /opt/dispatch/backups -name 'nightly-*.dump' -mtime +14 -delete
