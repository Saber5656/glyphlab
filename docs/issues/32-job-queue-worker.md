# Title

Job queue, worker, lease recovery, ingest & build handlers

# Summary

Implement the DESIGN §14.1/§14.3 execution engine: DB-table queue with atomic claim, a
dispatcher that runs each job in a **spawned child process** (default concurrency 1,
env-tunable) with a kill-enforced hard timeout, lease-expiry recovery, and the two job
handlers (`ingest`, `build`) whose pure core-library work runs in the child while all
DB/store writes happen in the parent.

# Context

This is where the hosted service actually does the work. Process isolation is what makes the
150 s hard timeout real (terminate the child; no abandoned threads mutating state) and
contains untrusted-image parsing (T1/T5). Lease recovery is what makes a PaaS restart
survivable (research/03 job-loss risk).

# Scope

`packages/service/src/glyphlab_service/jobs/{queue.py,worker.py,handlers.py}` + job status
endpoint `GET /api/projects/{id}/jobs/{job_id}` + tests.

# Detailed Requirements

1. `queue.py`: `claim_next(session) -> Job|None` with the §14.3 UPDATE-returning pattern
   (sqlite: `BEGIN IMMEDIATE` + select/update; postgres: `FOR UPDATE SKIP LOCKED`) —
   **claiming increments `attempts`** (queued→running is the only transition that does);
   `finish(job, status, error_code=None)`; `requeue_expired(session) -> int` (lease
   passed: `attempts < 2` → back to `queued`, else `failed`/`E_JOB_LOST`); lease = 180 s,
   renewed every 30 s by the dispatcher while the child runs. The dispatcher loop calls
   `requeue_expired` on startup and then every 30 s (the sweeper's hourly call is the
   backstop).
2. `worker.py`: `Worker(app_state)` — a dispatcher thread polling `claim_next` every 500 ms
   (backoff to 2 s when idle), running at most `settings.job_concurrency` (default **1**)
   child processes via `multiprocessing.get_context("spawn")`:
   - The child runs a registered pure function `run_job_payload(req: ChildRequest) ->
     ChildResult` with **no DB session and no ObjectStore client**; the parent does every
     DB/store write. IPC contract (picklable dataclasses in `jobs/ipc.py`):
     `ChildRequest = IngestRequest{upload_bytes: bytes, sidecar_json: bytes,
     charset_id: str, status_snapshot: dict[int, str]} | BuildRequest{svgs:
     dict[int, bytes], family_name: str, version: int, charset_id: str}`;
     `ChildResult = IngestResult{report: dict, svgs: dict[int, bytes]} |
     BuildResult{ttf: bytes, woff2: bytes, proof_html: bytes, qa_json: bytes,
     qa_passed: bool} | ChildError{code: str, detail: dict}`. Progress: the child writes
     one-line JSON stage markers (`{"stage": "trace"}`) to a pipe the parent reads (used
     for the timeout error-code decision).
   - Hard timeout: parent waits ≤ 150 s (`join`), then `terminate()` → 5 s → `kill()`;
     marks the job `failed` (`E_TRACE_TIMEOUT` if the child reported reaching the trace
     stage via a progress pipe message, else `E_INTERNAL`). Child death by signal/OOM →
     `failed`/`E_INTERNAL`.
   - Lease renewal every 30 s in the parent while the child runs; graceful shutdown on
     lifespan exit: stop claiming, terminate children after ≤ 10 s grace, leases recover
     on next boot.
3. `handlers.py` (parent-side orchestration around the child call):
   - `handle_ingest(job)`: parent loads upload bytes + sidecar (30's `get_sidecar`) and a
     status snapshot → child runs core `ingest_scan` (with an in-memory sink seeded from
     the snapshot; `force=False`) → returns report + SVG bytes → parent **re-applies the
     §8.3 gate against CURRENT rows** (double gate: the snapshot may be stale if a review
     happened mid-job; parent is the authority), writes SVGs to store
     (`glyphs/U+XXXX.svg`), upserts rows, stores the report into `jobs.payload.result`,
     sets upload row `processed` (+ `page_index`). **The original upload bytes are deleted
     from the store on EVERY terminal state — success AND failure** (§14.4 data
     minimization; sha/size row kept). Page-level `GlyphlabError` from the child → job
     `failed` with its code; upload row `failed`.
   - `handle_build(job)`: parent reads glyph SVGs (service policy: `accepted` + `auto`) →
     child parses them (restricted parser), runs core `build_font` +
     `run_qa(require_bakery=True)` + `generate_proof`, returns artifact bytes + QA report →
     parent persists artifacts (ttf, woff2, proof_html, qa_json) with `artifacts.job_id =
     job.id` (§14.2 build grouping), prunes to the 3 newest builds (§34 listing contract),
     writes result summary. QA fail → job `failed`
     `E_QA_FAILED` but artifacts + qa_json still persisted (§10.1 parity with CLI).
4. Job status endpoint per §15, behind issue 29's auth dependency: the job row must
   belong to the token-resolved project or uniform 404 (§17.3 T12). Response:
   `{status, error_code?, result?}` where result is present on terminal states (ingest:
   report counts; build: artifact ids + qa summary). Tests cover schema + cross-project
   404.
5. Tests: claim atomicity under 8 threads × 100 jobs (no double-claim; sqlite + postgres in
   CI); lease expiry → requeue → attempts cap → `E_JOB_LOST`; ingest happy path on corpus
   page; accepted-glyph protection on re-upload; build produces 4 artifacts and prunes to 3
   builds; original upload bytes gone after ingest; **timeout path with a child that sleeps
   forever → terminated within 160 s and job `failed`** (marked `slow`, uses a 2 s test
   timeout override); child-crash path (`os._exit(1)` stub) → `E_INTERNAL`.

# Acceptance Criteria

- [ ] Zero double-claims in the concurrency test on both engines.
- [ ] Kill-and-restart test (drop worker mid-job, expire lease, restart) completes the job
      exactly once end-to-end.
- [ ] Timeout terminates the child process (no glyphlab child processes remain — asserted
      via the child pid); job marked failed with the specified code.
- [ ] Upload originals absent from store post-ingest; glyph SVGs present; statuses correct.
- [ ] Build failure via QA leaves inspectable qa_json artifact and job error `E_QA_FAILED`.

# Validation

```bash
uv run pytest packages/service/tests/jobs -q
```

# Dependencies

15, 16, 17, 18, 27, 28, 29 (auth for the status endpoint), 30 (`get_sidecar`). (31 feeds
real jobs but is not required to build/test the worker.)

# Non-goals

Rate/queue admission (31/35), retention sweeps (36 — reuses `requeue_expired` cadence),
multi-process scaling (NG8/D7).

# Design References

DESIGN §14.1, §14.3, §14.4 (original deletion), §8.3, §10.1, §21 (budgets), ADR-005.
