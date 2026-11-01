# TITAN v0.3 verification report — 2026-10-31

## Baseline and final suite

Before modification: `python -m unittest discover -s tests -v` — **41 passed**.

Final run: same command — **82 passed, zero failures, zero skips in this environment**. Raw output: `docs/evidence/unittest.txt`. Includes the original four tests, the prior platform tests and the new project/artifact/scheduler/team/provider/coding/security/deployment cases.

**Real local execution:** SQLite persistence, competing claims, abrupt worker-process exit/recovery, checkpoint fencing, watchdog, controls, DAG validation, recurring scheduling, child task delegation, memory scope/expiry, authenticated HTTP missions and downloads, SHA-256 validation, artifact path/symlink/quota checks, secret-file loading, rate limiting, deterministic calculations, backtests, markdown creation, FFmpeg H.264/AAC rendering and SQLite backup/reopen.

**Mocked external boundaries:** six remote model adapters, model debate, failover, benchmark responses, coding proposal responses, local-model configuration guard, GitHub REST writes, MCP handshake, successful dispatch in approval tests and DNS responses in SSRF tests. Mock tests validate logic and boundaries. They are not evidence of live providers, cloud APIs, natural voices or sandbox isolation.

## Integrated demonstration

`python -m tests.demo_extended` — **passed**. Through the actual authenticated HTTP API:

1. Created a project and stored provenance.
2. Submitted a durable team with three children: statistics, report and paper backtest.
3. Completed all children and the parent.
4. Rendered a real three-second MP4.
5. Downloaded all three artifacts and checked hashes.
6. Backed up and reopened the database, preserving completed parent/child results.

Files: `docs/evidence/integrated-demo.json`, `report.md`, `paper-backtest.json`, `titan-preview.mp4`.

`ffprobe` verified H.264 video, 360×640 pixels, AAC audio and 3.000-second duration. One extracted frame was visually inspected: text is readable and within frame. This is an animated title-card demonstration with synthetic tone audio, not natural speech or AI HOUSE animation. Model calls: **zero**.

## Performance

`python -m tests.measure` executed 100 local 100-number analysis missions. Final captured run: about **104.6 missions/second**, median **8.99 ms**, p95 **13.13 ms** worker time. See `docs/evidence/performance.json` for exact values. An earlier run measured 123/s; normal runtime variation means neither is a production guarantee. No cloud load, model latency or multi-tenant capacity claim is made.

## Static and configuration checks

- `python -m compileall -q titan` — passed.
- `node --check titan/web/app.js` and `node --check titan/web/sw.js` — passed.
- YAML parse of Compose and CI — passed.
- Tests verify non-root Docker settings, read-only service filesystems, dropped capabilities, loopback host binding, no Docker socket mount, health check definition, frontend ID references, manifest assets and shell-only caching rules.
- Docker build, `docker compose config`, containers and health/restart behavior were **not executed here**: Docker CLI and daemon are absent. CI contains these checks, but no remote CI run exists yet.

## Browser verification blocked

Local Playwright is installed but Chromium is absent. The previous official install attempt returned an invalid/truncated archive. The cloud-browser attempt to open the local dashboard was rejected by automatic approval review because its review service hit a usage limit. No alternate browser route was used to bypass that rejection. Browser layout, PWA installation, blob previews, notifications, UI click flows and real browser E2E remain **unverified**. Syntax and API checks do not replace them.

## External checks

GitHub account lookup succeeded; `rebelloangel4-boop/titan-ai` returned 404. No repository creation capability is exposed by that connector. Render workspace lookup succeeded, but no service was created, selected for modification or billed. No provider credentials were configured. No external model inference, Telegram message, Drive operation, GitHub write, cloud deployment or purchase occurred.

## Defects corrected

- API chat messages now commit atomically with successful mission completion; stale workers cannot append them.
- Repeat artifact creation is deduplicated by job/name/content hash.
- Parent cancellation propagates to delegated children.
- Entire workflow dependency graphs are checked before execution.
- Authentication failures are rate-limited and connection concurrency is bounded.
- HTTP writes no longer hold the shared authentication lock.
- Secret sources reject symlinks/nonregular files and conflicting sources.
- Sandbox proxy variables are cleared; image digests are strictly checked; host fallback remains forbidden.
- Model benchmarks influence quality only for the matching model ID and fixed suite hash.
- Context truncation is explicitly labelled; full debate checkpoints are retained.
- Schema migration writes are serialized.

## Unresolved limitations

No known failing local test remains. This is **not** proof that all critical/high-severity production vulnerabilities are fixed. Public deployment is not approved as production-ready: secrets/memory at rest, multi-user controls, trusted egress, sandbox runtime, dependency image pinning and external penetration/load testing remain necessary. See docs/SECURITY.md and PROJECT_STATUS.md. General autonomous source changes and production code promotion are not enabled.

## Retrieval follow-up — 2026-10-31

Re-executed the unchanged baseline: 82 passed. After ranked project-memory retrieval: **89 passed**, zero failures, zero skips. Seven new tests exercise relevance beyond exact phrase matching, project/expiry boundaries, explicit truncation budgets, empty/unmatched queries, argument validation, preservation of literal search, and memory delivery to chat/planning as data. Chat/planner provider responses are fixtures, not live inference. Raw final output remains docs/evidence/unittest.txt. Browser, Docker and external service limitations above are unchanged.

## Independent engineering milestone — 2026-11-01

- Local suite: **99 passed**, zero failures/skips; raw output docs/evidence/unittest.txt.
- Five new snapshot tests: database/artifact roundtrip, preserve existing destination, reject corrupted artifact, reject artifact symlink, malicious archive cleanup.
- Five new Google refresh tests: concurrent single refresh, expiry/credential rotation, missing configuration, error redaction, request format/response validation. All HTTP responses mocked; no Google request occurred.
- Real Docker run 41280452654 exposed an output-flood cleanup deadlock. Fixed by terminating/releasing the attached client before container removal.
- Follow-up https://github.com/rebelloangel4-boop/Titan/actions/runs/41280541414 passed all three jobs. Four sandbox tests exercised nonroot UID, no injected host secret, cleared proxy, read-only root/source, disabled networking, nonzero exit propagation, one-use approval, output ceiling and no leaked container.
- Existing mobile/desktop Chromium workflow passed. Expanded project switching, artifact preview persistence/download, schedule controls and lock cleanup checks added; results must be checked on their commit.
- No real model, Google Drive, Telegram or persistent hosting verification.
