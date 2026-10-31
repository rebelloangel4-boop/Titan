# v0.3 changes

Preserves the original four tests and v0.2 queue/approval/debate behavior. Adds workspaces, scoped knowledge, private artifacts, recurring schedules, delegated team missions, bounded model plans, persistent chat, failover/circuit breaker/context limits, local-model adapter, frozen model benchmark, approved Python coding repair, private draft PRs, deterministic documents/backtests/video, secret-file loading, watchdog/health and Docker deployment configuration.

Baseline: 41 tests. Final checkpoint: 82 tests. Live external models/tools/deployment: unverified. Explicit acceptance ledger: 21/40 (52.5%), equal weight, no partial credit.

Upgrade: back up the database and artifacts, stop old workers, deploy source, then let schema initialization add new tables/columns before starting workers. New schema additions are serialized. Existing v0.2 jobs with no project map to the default workspace in display/retrieval. Retain prior code and backups; do not assume an older version understands new mission kinds. Restore a compatible backup for a complete downgrade.
