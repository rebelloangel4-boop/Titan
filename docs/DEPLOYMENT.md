# Deployment runbook

## Private repository

Create `titan-ai` as **Private** under `rebelloangel4-boop` and grant the connected GitHub integration access to this one repository. This operation remains outstanding. A source package and Git bundle preserve the work until access exists. On a trusted workstation/host with authenticated Git:

```bash
git clone titan-ai.git.bundle titan-ai
cd titan-ai
git remote remove origin
git remote add origin https://github.com/rebelloangel4-boop/titan-ai.git
git push -u origin main
```

Do not embed tokens in remote URLs. Use GitHub App authentication or a repository-scoped fine-grained token via a credential helper. The standalone `github.read` connector needs its own token and `TITAN_GITHUB_REPOSITORY`; it does not inherit ChatGPT's connector.

## Oracle VM / Linux

Confirm Always Free eligibility in the tenancy and home region. Select an eligible shape within current quotas; capacity may be unavailable. Do not enable paid fallback automatically. A 1 OCPU small-memory VM is sufficient for this lightweight orchestrator; external inference and heavy rendering are separate workloads.

1. Install Python 3.12, Git and Caddy from trusted sources. Create a dedicated `titan` system user.
2. Put the verified source under `/opt/titan`, root-owned and not writable by the service. Create `/etc/titan` with restricted access.
3. Copy `.env.example` to `/etc/titan/titan.env`, set mode `0600`, and configure secrets there or via a proper secret manager. Generate a token with `python -c 'import secrets; print(secrets.token_urlsafe(32))'` on that host. Never include this output in logs/screenshots.
4. Copy `deploy/titan.service` to the system service directory. Review paths/user. Run `systemctl daemon-reload` and `systemctl enable --now titan` as administrator.
5. Verify the authenticated API over loopback before exposure. Configure the real domain in `deploy/Caddyfile`. Use trusted TLS and firewall off public port 8787; only the reverse proxy should reach it.
6. Add edge authentication/rate limiting appropriate to the deployment. The bundled stdlib HTTP server is a private alpha server, not an internet-hardened application server. For production, replace it with a mature ASGI stack and load-test it.
7. On Android, open the HTTPS domain in Chrome, connect with the token, then use Add to Home screen / Install if offered. Actual installability must be tested after deployment.
8. Reboot the host and verify queued missions resume, stored memory persists and no completed tool invocation is replayed without renewed approval.

The supplied systemd service disables sandbox execution by default. Do not give the API user unrestricted root Docker access. Use a dedicated restricted/rootless sandbox worker or a separately isolated VM, and test the isolation before enabling it.

## Backup and rollback

```bash
python -m titan.backup /var/lib/titan/titan.db /secure-backups/titan-YYYYMMDD.db
```

The backup API includes committed WAL data and checks integrity. Store encrypted backups off the VM using an authorized destination and retention policy; Oracle idle VMs can be reclaimed. No backup upload or recurring timer has been configured.

For DB restore, stop the worker, archive the current DB and sidecar files together, restore a validated backup, fix owner/mode and restart. Never overwrite a running SQLite database. For source rollback, deploy a reviewed prior Git commit. Database migration rollback must be reviewed separately. Routing-policy rollback is available in the authenticated Benchmarks screen.

## Why not Actions as a 24/7 server?

CI runners are ephemeral, metered and time-limited. Use Actions for verification, not a daemon or durable SQLite storage. No scheduled workflow is included that would create an illusion of persistent operation. Cloudflare Workers also requires a different backend/storage architecture; this Python SQLite service is not a drop-in Worker.


## v0.3 Docker Compose path

Docker CLI/runtime was unavailable in the build session. These are prepared operator commands, not evidence of a successful deploy. Tests checked YAML structure and selected security properties.

1. On the authorized Linux host, copy `.env.example` to `.env`. Leave `TITAN_TOKEN` empty and set only required provider settings. Compose supplies `TITAN_TOKEN_FILE`.
2. Create `.secrets` with mode 0700. Generate a random token into `.secrets/titan_token`, mode 0600. Set `.env` to 0600. Do not print or share these values.
3. Run `docker compose config --quiet`, then `docker compose build` and `docker compose up -d`.
4. API binds to loopback host port 8787. Worker starts after API health passes. Both use the `titan_data` volume; SQLite is on a local volume, not an unsupported network filesystem.
5. Put a reviewed TLS reverse proxy in front. The image runs as UID 10001, with read-only root, dropped capabilities, no Docker socket mount and bounded resources. CI includes container smoke checks but has not executed remotely.
6. Confirm `/healthz` and authenticated `/api/health`, complete a real mission, restart services, and confirm durable state. Back up the SQLite DB **and** artifact directory; a database-only backup does not restore artifact bytes.
7. The optional sandbox remains disabled in this stack. A Docker client/socket is deliberately not installed/mounted in the application container. Provide a separately isolated execution design before enabling arbitrary generated code.

This is still a private alpha service. A connection to Render exists, but its source-repository requirement is unmet, and persistent worker/storage choices must be reviewed against the ₹0 constraint. No Render service was created.
