# Operations runbook

Run commands from the repository root. The image uses Node 22 for its build stage
(the supported LTS baseline) and Python 3.12 for runtime. Runtime writes are confined
to `/data` and `/tmp`; one web process and one job child run by default.

## First deploy

**[HUMAN]** Install flyctl, create a Fly.io account and configure payment.
**[HUMAN]** Choose an available app name and region; replace `glyphlab`/`nrt` in
`deploy/fly.toml`. A production deployment incurs charges.

```bash
fly launch --no-deploy --copy-config --config deploy/fly.toml
fly volumes create glyphlab_data --size 3 --region nrt
fly deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile .
curl --fail https://YOUR_APP.fly.dev/healthz
```

**[HUMAN]** No secrets are required for the default local object store and SQLite.
An optional PostgreSQL deployment needs `GLYPHLAB_DATABASE_URL` plus the service
`postgres` extra. Never put credentials in files or shell history; use the provider's
secure secret input. Use the application's create-project form, download its template,
and confirm the downloaded file is a PDF before announcing an instance.

## Custom domain

**[HUMAN]** Register and configure DNS for your domain, then:

```bash
fly certs add YOUR_DOMAIN
fly certs check YOUR_DOMAIN
```

HTTPS is required. Proxy trust is enabled only on Fly, whose edge overwrites the
client-IP header. Direct Docker self-hosting leaves proxy trust disabled.

## Upgrades

Check out a reviewed release tag, back up the volume, and run:

```bash
fly deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile .
fly status
fly checks list
```

The Python entrypoint runs Alembic before starting one uvicorn process. Do not scale
this application across machines sharing SQLite. Roll back code only when its migration
is backward-compatible; otherwise restore the matching snapshot and release together.

## Storage growth

**[HUMAN]** To use a fresh S3-compatible instance, provision Tigris with
`fly storage create`. Store `GLYPHLAB_S3_SECRET_ACCESS_KEY` through Fly secrets.
Set `GLYPHLAB_OBJECT_STORE=s3`, `GLYPHLAB_S3_ENDPOINT_URL`, `GLYPHLAB_S3_BUCKET`,
`GLYPHLAB_S3_REGION`, and `GLYPHLAB_S3_ACCESS_KEY_ID` in the deployment environment,
then deploy. These fields are the same names used by `Settings`.

Existing local project objects are not migrated automatically. Keep the old local-store
instance running until its projects expire, and start a separate fresh S3 instance;
do not switch an existing instance's backend and strand its active projects.

## Backup & restore

```bash
fly volumes snapshots list VOLUME_ID
fly volumes snapshots create VOLUME_ID
```

SQLite uses WAL. Take snapshots while the service is healthy, preferably after pausing
new work and completing jobs; verify restoration to a separate volume before replacing
the live volume. **[HUMAN]** Select the snapshot, restore a replacement volume using
`fly volumes create glyphlab_data --snapshot-id SNAPSHOT_ID`, then attach it to the
matching release. Never delete the original volume before validating project/template
and font downloads from the restoration.

## Incident playbooks

### 1. Service failure

Run `fly logs`, `fly status`, and `fly checks list`. Use `fly ssh console` for inspection.
Check writable `/data` and `/tmp`, migration status and available memory. Increase the
VM memory with `fly scale memory 2048` only after **[HUMAN]** cost approval.

### 2. Disk full

A storage-watermark rejection returns 507. Inspect `fly volumes list` and expiry jobs.
Increase capacity with `fly volumes extend VOLUME_ID --size 6` after **[HUMAN]** approval,
or lower `GLYPHLAB_MAX_STORE_BYTES` to reserve space. Never manually remove active
project files to bypass quotas.

### 3. Token leak

A token is unrecoverable and there is no admin token lookup. The user should open the
project with their saved token and use Delete now. Create a replacement project if
needed; deletion is the only supported revocation. Do not log or request the secret.

### 4. Abuse spike

Inspect redacted abuse events and logs. Tune `GLYPHLAB_RL_CREATE_PER_DAY`,
`GLYPHLAB_RL_UPLOADS_PER_HOUR_IP`, `GLYPHLAB_MAX_UPLOADS_PER_PROJECT`, and
`GLYPHLAB_MAX_STORE_BYTES`; redeploy after changing environment values. Check proxy
trust before interpreting IP rates. Never disable authentication or image validation.

## Cost

| Resource | Planning allowance |
| --- | --- |
| One shared VM, 1 GiB RAM, 3 GB volume | Rough initial budget: USD 5–7/month |
| Traffic, snapshots, optional external storage | Additional usage-dependent charges |

This is a planning placeholder, not a verified current quote. **[HUMAN]** Check provider
pricing before provisioning. No production resources are created by the implementation.
Cloud Run is architecturally possible but is not a supported deployment target in v1.
