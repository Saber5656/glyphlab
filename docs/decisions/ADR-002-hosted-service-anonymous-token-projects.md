# ADR-002: Public hosted service with anonymous token projects and TTL retention

- Status: Accepted (2026-07-08)
- Deciders: user (requirements interview), Fable (design)

## Context

The user chose a **publicly hosted service** as the web delivery model (over local-only server
or static client-side site), while requirements also demand strong privacy (handwriting is
personal data), OSS-friendly operations at personal/small-community scale, and a v1 that is
*deploy-ready* rather than *deployed*.

## Decision

1. No accounts. A project is identified by a UUID and authorized by a **single 256-bit bearer
   token** (`glp_` + base64url of 32 random bytes), shown once at creation, stored hashed
   (SHA-256) server-side.
2. Projects expire: `expires_at = last_accessed + 14 days` (env-tunable); hourly sweeper purges
   data and object-store prefixes; users can purge immediately via `DELETE /projects/{id}`.
3. Original uploaded images are deleted as soon as ingest completes; only derived cell/glyph
   data is retained (data minimization).
4. Unknown-id and wrong-token responses are indistinguishable (uniform 404) to prevent
   enumeration; tokens travel only in the `Authorization` header, or the URL **fragment** for
   shareable links (never sent to the server).
5. v1 completion = the service is deployable (Docker, fly.toml, runbook); contracting a host,
   setting secrets, and going live are human tasks after v1.

## Consequences

- No PII beyond the handwriting itself and short-lived abuse logs; no password storage, no
  email flows — large scope and attack-surface reduction.
- Losing the token = losing the project (mitigated by localStorage + explicit save-this UX);
  acceptable for an auto-expiring artifact whose end product is a downloaded font.
- The `projects` table stays self-contained, so v2 accounts (D4) can be layered by adding an
  `owner` column without breaking token access.
- The DB schema, retention sweeper, and rate limits become mandatory v1 issues, not hardening
  afterthoughts.

## Alternatives rejected

- **Accounts (OAuth/email)**: better continuity, but adds authn, deletion/GDPR workflows, and
  email infrastructure — disproportionate for v1.
- **Local-launch web / static WASM site**: rejected by the user's product choice; the design
  still keeps docker-compose self-hosting first-class for P3.
