# DISPATCH on Hetzner

Server: Hetzner CX23 `89.167.23.152` (Ubuntu 24.04), shared with TrueFans RADIO (Icecast on :8000), the Live Music Hub and TFC Festivals.
Live at https://dispatch.89-167-23-152.sslip.io (sslip.io resolves to the server's IP, so no DNS record is needed).

| Where | What |
|---|---|
| `/opt/dispatch/app/` | The code, sent by `deploy.sh` (don't edit here; it's overwritten) |
| `/opt/dispatch/dispatch.env` | All env vars, including `POSTGRES_*` and `DATABASE_URL` (mode 600) |
| `/opt/dispatch/pgdata/` | Postgres 18 data |
| `/opt/dispatch/backups/` | Nightly `pg_dump` at 03:30, kept 14 days (`/etc/cron.d/dispatch-backup`) |

The app listens on 8090 (8000 is Icecast), bound to 127.0.0.1 only. Public HTTPS comes from the hub's Caddy
(`tfc-hub-caddy-1`). Its Caddyfile lives in the **TFC-LIVE-MUSIC-HUB** repo at `ops/hetzner/Caddyfile`, so DISPATCH's
block has to stay there or the next hub deploy removes it.

## Everyday

```
sh ops/hetzner/deploy.sh                 # send code, rebuild, wait for /health/ready
ssh root@89.167.23.152 'cd /opt/dispatch/app/ops/hetzner && docker compose -p dispatch logs -f web'
```

Change an env var: edit `/opt/dispatch/dispatch.env` on the server, then `docker compose -p dispatch up -d web` in that folder.
Admin password still rotates through the `admin_settings` DB row, not env vars.

## Database

- `sh ops/hetzner/migrate-db.sh` copies Railway's Postgres over this one (**replaces** it). Only useful until Railway is shut down.
- Restore a backup:
  `docker compose -p dispatch exec -T db sh -c 'pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists --no-owner' < /opt/dispatch/backups/<file>.dump`

## Moving to truefansdispatch.com

1. Point an A record at `89.167.23.152` (grey cloud / DNS only if it's on Cloudflare).
2. In the hub repo's Caddyfile, change `dispatch.89-167-23-152.sslip.io` to `truefansdispatch.com, www.truefansdispatch.com`, copy it to
   `/opt/tfc-hub/app/ops/hetzner/Caddyfile`, then `docker exec tfc-hub-caddy-1 caddy reload --config /etc/caddy/Caddyfile`.
3. Set `WEEKLYAMP_SITE_DOMAIN=https://truefansdispatch.com` in `dispatch.env` and restart `web`.
