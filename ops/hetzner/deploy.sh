#!/bin/sh
# Deploy DISPATCH to Hetzner (replaces Railway's git-push deploy). Run from the project folder on your Mac:
#   sh ops/hetzner/deploy.sh
# Sends the code (never .env or local databases), rebuilds and restarts the web container, waits for /health/ready.
set -eu
HOST="${HETZNER_HOST:-root@89.167.23.152}"
cd "$(dirname "$0")/../.."

echo "== sending code to $HOST"
rsync -az --delete --exclude-from=.dockerignore --exclude 'test_*.html' ./ "$HOST:/opt/dispatch/app/"

echo "== building and restarting"
ssh "$HOST" 'set -e
  [ -s /opt/dispatch/dispatch.env ] || { echo "No /opt/dispatch/dispatch.env — create it first (see ops/hetzner/README.md)"; exit 1; }
  cd /opt/dispatch/app/ops/hetzner
  docker compose -p dispatch up -d --build
  docker image prune -f >/dev/null
  for i in $(seq 1 45); do curl -sf http://127.0.0.1:8090/health/ready && echo && exit 0; sleep 2; done
  echo "DISPATCH did not answer in 90s — logs:"; docker compose -p dispatch logs --tail 60 web; exit 1'
echo "== deployed"
