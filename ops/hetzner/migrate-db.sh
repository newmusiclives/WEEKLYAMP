#!/bin/sh
# Copy the Railway Postgres into the Hetzner one, replacing what's there. Run from the project folder on your Mac:
#   sh ops/hetzner/migrate-db.sh
# The dump runs on the server in a postgres:18 container (the Mac's pg_dump is too old for Railway's PG 18).
# A copy of the dump is kept at /opt/dispatch/backups/railway-<timestamp>.dump.
set -eu
HOST="${HETZNER_HOST:-root@89.167.23.152}"
SRC=$(railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-)
[ -n "$SRC" ] || { echo "Couldn't read DATABASE_PUBLIC_URL from Railway (run: railway link)"; exit 1; }

printf '%s' "$SRC" | ssh "$HOST" 'set -e
  SRC=$(cat); TS=$(date +%Y%m%d-%H%M%S); OUT=/opt/dispatch/backups/railway-$TS.dump
  docker run --rm -e SRC="$SRC" postgres:18 sh -c "pg_dump -Fc --no-owner --no-acl \"\$SRC\"" > "$OUT"
  echo "== dumped $(du -h "$OUT" | cut -f1) to $OUT"
  cd /opt/dispatch/app/ops/hetzner
  docker compose -p dispatch exec -T db sh -c "pg_restore -U \$POSTGRES_USER -d \$POSTGRES_DB --clean --if-exists --no-owner --no-acl" < "$OUT"
  docker compose -p dispatch exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -Atc \"select count(*) from pg_stat_user_tables\"" | sed "s/$/ tables restored/"'
