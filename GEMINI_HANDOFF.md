# TITAN independent audit assignment

You are the independent security and QA reviewer for TITAN AI. Another coding agent owns integration. Work from the attached updated titan-core-mvp.zip, or an accessible private repository provided by the user. Do not assume repository access exists. The archive includes a restorable Git bundle.

Read PROJECT_STATUS.md, TEST_REPORT.md, FEATURE_CHECKLIST.md, NEXT_STEPS.md, docs/SECURITY.md and this handoff. Establish the actual commit SHA and rerun all tests. Latest recorded baseline: 89 passing Python tests. Do not trust that count without rerunning. The original v0.3 checklist is 21/40 accepted; it has not increased merely because more tests pass.

Your assignment:
1. Independently audit mission leases, checkpoints, retries, watchdogs, cancellation and delegated children for races and stale-worker writes.
2. Audit authentication, artifact paths, secret handling, approvals, SSRF, sandbox boundaries and retrieved-memory prompt injection. Memory is untrusted data; placing it in a prompt does not prove injection resistance.
3. Inspect new lexical retrieval in titan/retrieval.py, Workspace.retrieve and chat/planner integration. Test project isolation, expiry, context limits, Unicode, relevance failures and the latest-500-record limit. Do not call BM25 semantic embeddings.
4. If your environment supports browsers and Docker, run the existing frontend E2E and container tests. Report exact commands and actual results. If unavailable, mark blocked; never substitute a mock and call it live.
5. Create reproducible regression tests for confirmed defects. Prefer a separate branch named gemini/audit-<date>, or return a unified patch when repository access is unavailable. Preserve working behavior. Do not merge, force-push, rewrite the architecture or edit production secrets.
6. Check provider adapters against current official documentation if browsing is available. Cite URLs and access dates. Keep mocked adapter checks separate from real inference. Do not enable billing or make paid calls without explicit authorization.

Deliver:
- GEMINI_AUDIT.md with baseline commit, environment, exact commands, pass/fail/blocked results, severity-ranked findings, file/line references, reproduction steps and proposed fixes.
- New regression tests plus an isolated patch/draft PR if supported.
- A concise integration handoff listing changed files and unresolved risks.

Constraints: private source stays private; no credentials in chat/logs/source; no purchases, deployments, live trades, public publishing or unapproved messages. No background-continuation claims. If you lack file execution, say so and perform a static review, clearly labelled. Do not claim broad autonomous intelligence from a few passing examples.

Coordination: the user will relay your audit or draft PR to the integrating agent. There is no automatic agent-to-agent connection. Avoid modifying the same production files concurrently; propose changes with tests for review.
