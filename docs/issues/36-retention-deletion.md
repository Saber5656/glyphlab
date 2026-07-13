# Title

Retention sweeper & deletion flows

# Summary

Implement DESIGN §14.4: the periodic sweeper (interval = `settings.sweep_interval_s`,
default 3600 s) that purges expired projects (store prefix + rows + tombstone), requeues
expired job leases (§14.3), trims `abuse_events` rows older than 7 days (§17.7) and
tombstones older than 30 days, and maintains the global storage-pressure flag.

# Context

Auto-expiry is a core privacy promise (ADR-002) and the answer to unbounded anonymous
storage. It must be boring, observable, and crash-safe.

# Scope

`packages/service/src/glyphlab_service/sweeper.py` + lifespan wiring + tests.

# Detailed Requirements

1. `Sweeper(session_factory, store, settings, app_state)` — asyncio task started in app
   lifespan, ticking every `settings.sweep_interval_s` (first tick 60 s after boot), each
   tick:
   a. `requeue_expired(session)` from issue 32 (lease recovery per §14.3; the worker also
      runs it on its own cadence — this is the backstop).
   b. Select projects `expires_at < now` (limit 50/tick; a purged project has no row at
      all — §14.2 keeps tombstones in their own table) → for each:
      `purge_project` (store prefix first, then rows, then tombstone — order matters: a
      crash between store-purge and row-delete self-heals on the next tick because rows
      still mark it expired; document this invariant in code).
   c. Delete tombstones older than 30 days AND `abuse_events` rows older than 7 days
      (§17.7 promise; the rows are written by issues 29/35).
   d. Emit one JSON log line: `{swept: n, requeued: m, tombstones_trimmed: k,
      abuse_trimmed: j, duration_ms}`.
2. Crash-safety: each project purged in its own transaction; a failing store delete logs
   `error_code` and leaves the project for the next tick (no partial row deletion).
3. Clock injection: sweeper takes a `now()` callable for tests; no direct
   `datetime.utcnow()` in logic.
4. Sweep concurrency guard: single in-process task; a second `Sweeper.start()` is a no-op
   (idempotent), and ticks skip if the previous tick still runs.
5. Disk watermark (T4 tail): each tick computes store usage (local: directory walk of the
   store root, cheap at our scale; s3: skip, flag stays False) and sets
   `app_state.storage_pressure = usage > settings.max_store_bytes` (both defined in issue
   26; issue 31 is the consumer and defaults to False before this issue lands).
6. Tests (frozen clock): project past expiry purged with store-prefix deletion verified;
   half-crashed purge (store deleted, rows present) heals next tick; active project
   untouched; tombstone + abuse_events trim lifecycle; watermark flag flips and upload
   507s (integration test with 31's endpoint); sweep log line shape.

# Acceptance Criteria

- [ ] Expiry → purge → tombstone → trim lifecycle fully covered by clock-driven tests
      (incl. abuse_events 7-day trim).
- [ ] Crash-ordering invariant (store-first) implemented and tested.
- [ ] Watermark integration returns 507 on uploads under pressure.
- [ ] Exactly one sweeper task under double-start.

# Validation

```bash
uv run pytest packages/service/tests/test_sweeper.py -q
```

# Dependencies

27, 28, 29 (`purge_project`), 32 (`requeue_expired`). (Issue 31 consumes the
storage-pressure flag; the flag itself lives in 26's app state, so there is no dependency
edge — only the integration test here exercises 31's endpoint.)

# Non-goals

User-configurable retention per project (fixed global default in v1), backup/restore
(runbook documents volume snapshots — 46).

# Design References

DESIGN §14.3 (lease recovery), §14.4, §17.3 T4, §17.7 (abuse-log retention), ADR-002,
ADR-005.
