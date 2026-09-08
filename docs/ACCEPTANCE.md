# Product acceptance evidence

Tested commit: `bfbd3fde8e0c3720e1a6ddba79a05da801b6ceb5`
Run started (UTC): 2026-09-08T04:30:57.011216+00:00

This report records the immutable commit executed. A later report-only commit
may add this document without changing the tested implementation; it does not change
the tested commit to the report commit. Any implementation change requires a new run.

| Item | DESIGN reference | Result | Evidence | Measurement |
|---|---|---|---|---|
| T1 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t1_decompression_bomb, test_t1_polyglot[\x89PNG\r\n\x1a\nPKzip], test_t1_polyglot[\xff\xd8\xfftruncated], test_t1_polyglot[<svg><script>alert(1)</script></svg>]; container: requires_inprocess; skipped |
| T10 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t10_t11_repo_guards; container: requires_inprocess; skipped |
| T11 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t10_t11_repo_guards; container: requires_inprocess; skipped |
| T12 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t12_cross_project; container: test_t12_cross_project |
| T2 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t2_token_bruteforce; container: requires_inprocess; skipped |
| T3 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t3_no_token_leak; container: requires_inprocess; skipped |
| T4 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t4_quota_walls; container: requires_inprocess; skipped |
| T5 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t5_timeout_boundary, test_t5_trace_bomb_cells; container: requires_inprocess; skipped |
| T6 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t6_traversal; container: requires_inprocess; skipped |
| T7 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t7_xss_name_and_headers; container: test_t7_xss_name_and_headers |
| T8 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t8_no_public_artifacts; container: test_t8_no_public_artifacts |
| T9 | 17.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/abuse-inprocess.log | in-process: test_t9_no_egress; container: requires_inprocess; skipped |
| cli-clean-scan | 18.3 / 20 | pass | work/acceptance/20260908T043057Z-bfbd3fde/wheel-result.json | 6 pages; 272 encoded; wheel sha256 8ee155e9786a52e8e5338b94f7aa06812a3ccd53d953d7c31e2ec107ec8facb9 |
| cli-phone-tilt | 18.3 / 20 | pass | work/acceptance/20260908T043057Z-bfbd3fde/wheel-result.json | 6 pages; 272 encoded; wheel sha256 8ee155e9786a52e8e5338b94f7aa06812a3ccd53d953d7c31e2ec107ec8facb9 |
| container-hardening | 17.5 | pass | work/acceptance/20260908T043057Z-bfbd3fde/container-inspect.log | user=10001; readonly=True |
| dependabot | 17.3 T10 | pass | work/acceptance/20260908T043057Z-bfbd3fde/dependabot-tracked.log | sha256 1f50be2313dd81201c463b67c161e8fb74fa000b47d33c396ae32bc9de279c89 |
| gitleaks-main | 17.3 T11 | pass | work/acceptance/20260908T043057Z-bfbd3fde/gitleaks-main-jobs.log | https://github.com/Saber5656/glyphlab/actions/runs/34187161341/job/101937712981 at bfbd3fde8e0c3720e1a6ddba79a05da801b6ceb5 |
| hosted | 18.3 / 16 | pass | work/acceptance/20260908T043057Z-bfbd3fde/playwright.log | all configured Chromium, WebKit, mobile projects |
| npm-audit | 17.3 T10 | pass | work/acceptance/20260908T043057Z-bfbd3fde/npm-audit.log |  |
| performance-build | 21 | pass | work/acceptance/20260908T043057Z-bfbd3fde/wheel-result.json | 4.116 s; budget 10s; gate 15.0s |
| performance-ingest | 21 | pass | work/acceptance/20260908T043057Z-bfbd3fde/wheel-result.json | 0.826 s; budget 15s; gate 22.5s |
| performance-memory | 21 | pass | work/acceptance/20260908T043057Z-bfbd3fde/container-memory.json | peak sampled 238.30 MiB; ceiling <800 MiB |
| performance-template | 21 | pass | work/acceptance/20260908T043057Z-bfbd3fde/wheel-result.json | 0.543 s; budget 5s; gate 7.5s |
| python-audit | 17.3 T10 | pass | work/acceptance/20260908T043057Z-bfbd3fde/python-audit.log | 0 explicitly listed repository exceptions |
| retention | 14.4 / 18.3 | pass | work/acceptance/20260908T043057Z-bfbd3fde/retention.json | TTL 0.001 days; sweep 5s; purge observed at 88.283s |
| workflow-hygiene | 17.3 T10/T11 | pass | work/acceptance/20260908T043057Z-bfbd3fde/workflow-hygiene.log |  |

## Release checklist (human decision)

- [ ] Version bump
- [ ] Release tag
- [ ] TestPyPI dry run
- [ ] PyPI approval
- [ ] First production deployment decision
- [ ] Announcement

These results use synthetic handwriting. Physical printing, real handwriting,
and real phone photographs remain outside this acceptance run.
