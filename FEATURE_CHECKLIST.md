# TITAN evidence-based acceptance checklist

**22/40 criteria accepted = 55%.** Equal weights; partial criteria get no credit. This is not a production-readiness percentage.

| # | Acceptance criterion | Status | Evidence or gap |
|---|---|---|---|
| 1 | Recover and verify prior source/tests | passed | 41-test baseline rerun |
| 2 | Durable mission queue | passed | SQLite reopen and competing-claim tests |
| 3 | Crash recovery and consistent backup | passed | Actual process exit and backup restore tests |
| 4 | Pause/resume/cancel including child tasks | passed | Control fencing and team cancellation tests |
| 5 | Mission watchdog | passed | Late model fixture cannot commit after deadline |
| 6 | Durable delegated tasks | passed | Real three-child integrated demonstration |
| 7 | Dependency-aware workflows | passed | Execution order and pre-execution cycle rejection |
| 8 | Recurring scheduling | passed | Atomic/coalesced ticks tested locally |
| 9 | Project-scoped searchable memory | passed | Scope, literal search and expiry tests |
| 10 | Private artifact storage/downloads | passed | Actual HTTP downloads; hash, quota and symlink tests |
| 11 | API authentication and rate limits | passed | 401/429/origin/path boundary tests |
| 12 | Secret-file loading | passed | Regular-file, symlink and conflict boundaries |
| 13 | API request quotas and spending reservations | passed | Zero-spend and concurrent reservation tests; not invoice reconciliation |
| 14 | Local numerical analysis | passed | Actual worker and HTTP tests |
| 15 | Local document creation | passed | Actual markdown artifact downloaded |
| 16 | Bounded local MP4 rendering | passed | Real 360x640 H.264/AAC output and frame inspection |
| 17 | Historical paper simulator | passed | Deterministic fee/causality tests on supplied sample prices |
| 18 | Fixed deterministic regression gates | passed | Passing/rejected candidates tested |
| 19 | Routing configuration promotion/rollback | passed | Versioned configurations and rollback tests |
| 20 | API-to-worker-to-artifact integration | passed | Integrated demonstration and restore transcript |
| 21 | Worker monitoring and local performance measurement | passed | Health staleness test and 100-mission measurement |
| 22 | Complete browser/PWA interaction and installability | partial | Mobile/desktop Chromium CI passes; expanded flows under test. Real Android installability remains unverified. |
| 23 | All six real provider connections | blocked | Adapters mocked; no live credentials |
| 24 | Real local/open-source model inference | blocked | Loopback adapter present; no installed model/runtime verified |
| 25 | Real independent model-to-model debate | blocked | Orchestration fixtures pass; no live conversation |
| 26 | Live failover and quality-based routing | blocked | Logic tested; needs live provider outage/benchmark evidence |
| 27 | Live high-level goal-to-artifact agent | blocked | Bounded planner tested with fixtures only |
| 28 | Sandboxed code generation/test/repair | partial | Real Docker execution and one-use approvals pass; live model-generated coding/repair still unverified. |
| 29 | Authorized GitHub push/draft PR and remote CI | partial | Public source publication explicitly authorized; push and remote CI verified. TITAN draft-PR adapter remains mocked. |
| 30 | Live browser/research/MCP automation | blocked | Subset adapter present; no live server validated |
| 31 | Durable Google Drive OAuth workflow | partial | Refresh-token exchange/cache implemented and fixture-tested; initial consent UI and live Drive workflow unverified. |
| 32 | Verified Telegram notifications | blocked | Approval-gated connector needs bot and destination |
| 33 | Natural-voice character animation/YouTube production | unfinished | Only technical title-card MP4 demonstrated |
| 34 | Indian institutional/market research and portfolio risk engine | unfinished | Only supplied-price long-only simulator available |
| 35 | General full-stack autonomous software delivery | unfinished | Current coding scope is single-file Python |
| 36 | Semantic long-term knowledge retrieval | unfinished | Ranked lexical BM25 retrieval implemented; semantic embeddings not yet implemented. |
| 37 | Live benchmark-driven improvement evidence | blocked | Frozen suite implemented; no live scores or demonstrated AI improvement |
| 38 | Docker build and runtime isolation verification | passed | GitHub run 41280541414: real Docker build/startup, UID, read-only root/source, network blocking, secret isolation, bounded output and cleanup tests pass. |
| 39 | Persistent cloud/TLS/reboot/off-host restore | blocked | No deployed service or verified destination |
| 40 | Production multi-user/security hardening | unfinished | Private alpha; mature public perimeter, encrypted storage and broader audit remain |
