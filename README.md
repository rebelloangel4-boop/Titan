# TITAN AI · private alpha v0.3

A functioning local mission-control platform with project workspaces, durable delegated tasks, recurring schedules, searchable memory, artifact management, provider failover, approved code testing, narrow regression gates and an Android-oriented dashboard.

**100 local tests pass. 21 of 40 documented acceptance criteria are verified (55%). No cloud deployment or live model inference has been verified.** See FEATURE_CHECKLIST.md for the precise denominator, PROJECT_STATUS.md for unfinished engineering and USER_ACTION_REQUIRED.md for account tasks.

A real authenticated API-to-worker demonstration creates reports, runs a paper simulation, renders a playable H.264/AAC MP4, verifies downloads and restores the database. The video is a technical animated title card, not natural-voice character production.

## Run locally

Python 3.12 recommended. Backend has no third-party dependencies.

```bash
python -m unittest discover -s tests -v
export TITAN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m titan.server --db titan.db
```

Open `http://127.0.0.1:8787` and enter the token from your local environment. Never put it in a URL or commit it. The UI keeps it only in tab memory; reload requires reconnecting. For Android access, deploy behind trusted HTTPS; `localhost` on your phone does not refer to a remote server. No public endpoint is supplied with this source package.

To verify a working mission without AI keys, choose **Numerical analysis**, use `{"values":[10,20,30,40]}`, and queue it. Expected mean and median: 25. The background worker persists the result. The same operation is exercised by authenticated HTTP tests.

## Real provider calls

Set API credentials in the server environment, not the dashboard: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`.

Check model availability in each provider account and set `TITAN_MODEL_GEMINI`, `TITAN_MODEL_GROQ`, etc. Inherited default IDs are compatibility defaults, **not promises of current availability**. ChatGPT subscriptions do not configure API credentials for this service.

Every provider is blocked by default by the zero-spend policy. After checking actual free quotas, an operator can set `TITAN_FREE_PROVIDERS=gemini,groq`. This is an operator assertion, not automatic verification of billing. Set provider-side hard spending controls as well. Paid use additionally requires `TITAN_DAILY_USD` and a conservative `TITAN_MAX_CALL_USD_<PROVIDER>` ceiling. The ledger reserves this ceiling before requests, retains failed/uncertain reservations, and caps daily request count (default 50, UTC reset). It does not reconcile actual invoices or guarantee a ceiling if you configure incorrect estimates.

Create a debate with `{"providers":["gemini","groq"]}`. Each model sees the objective independently first, then the other model's proposal, then criticism, followed by synthesis. Two providers require seven calls. Invalid structured responses remain visible as raw output labelled `schema_valid:false`. Model agreement is never marked independently verified. There is no fake-response mode in the server. Test doubles exist only in tests.

## Missions and recovery

- `analysis`: finite numeric statistics, no external API.
- `debate`: independent proposals, cross-examination, rebuttals, synthesis; no automatic execution of the plan.
- `tool`: one explicitly approved invocation.
- `chat`: persisted conversation using ranked providers and failover.
- `agent`: high-level goal to bounded analysis/document/video/backtest plan; model planning remains unverified until real keys are configured.
- `team`: up to eight durable delegated child missions; parent waits and reports child outcomes.
- `code`: single-file Python generation, exact sandbox approval, tests and up to three repair candidates; real sandbox execution/isolation passes CI; live model-generated repair remains unverified.
- `document`, `video`, `backtest`: real local deliverable workflows. Prices must be supplied; outputs are private.
- `model_benchmark`: frozen three-case exact-answer suite with per-model scoped routing quality. It does not measure universal intelligence.
- `workflow`: operator-defined DAG of analysis and approved tool steps. Full dependency validation precedes any action; completed steps are checkpointed.
- Scheduled start uses a timestamp. Recurring schedules are stored and coalesced by the running worker, with pause/enable controls and no accumulation of blocked instances.
- SQLite transactions ensure one active claim; leases, heartbeats, retry backoff, and maximum attempts govern recovery. Paused/cancelled workers cannot commit stale results. An in-flight external call may still finish and incur a charge.
- Tool approvals bind mission, tool name, and exact JSON argument digest. They are consumed before invocation. A crash requires a new approval rather than automatically replaying an uncertain external side effect.
- Short memory is excluded from retrieval after 24 hours. Long memory persists. Expiry is logical, not secure erasure.

Example workflow:

```json
{"steps":[{"id":"baseline","kind":"analysis","values":[24,26,25,25]},{"id":"candidate","kind":"analysis","values":[22,23,24,23],"depends_on":["baseline"]}]}
```

The worker processes one mission at a time per process. Multiple processes can share a local SQLite database, but this is not distributed HA, network-filesystem storage, or a high-throughput queue. Use PostgreSQL plus a dedicated queue when that becomes necessary.

## Tools and permissions

`github.read` is scoped repository metadata read; `github.propose` creates a new branch and draft PR in the configured private repository, with no merge/force-push and no critical-path writes; `drive.list` lists files using an externally supplied access token or configured refresh-token credentials; `web.read` reads allowlisted JSON endpoints; `telegram.send` sends to a server-configured chat only after approval; `sandbox.python` requires disabled-by-default Docker isolation and a pinned image; `mcp.call` exposes explicitly allowlisted remote tools. All require exact operator approval, including reads that transmit private context.

MCP supports the **2025-03-26 JSON HTTP subset**, including initialization, initialized notification, and session header. SSE, stdio, server-initiated requests and newer protocol versions are not implemented. Browser automation can be connected through an approved compatible MCP tool but no browser connector has been live-tested.

No live trading, transaction, destructive core action, merge or public publishing tool is implemented. The draft-PR write tool requires exact approval and has only fixture tests so far. Model output cannot authorize one.

## Improvement boundary

Failures and provider latency/reliability/reserved cost are recorded. Live quality scores remain unknown until real providers run the frozen benchmark. Fixture scores are confined to test databases. Fixed numerical benchmarks detect deterministic regressions. Routing weights have separate fixed synthetic preference tests, reviewed promotion, versioned previous settings, and rollback. These tests do **not** measure overall model intelligence or improve model weights. No self-modifying source code, automatic prompt promotion, or unattended production-core changes are enabled. The model benchmark is exact-answer task adherence, not broad intelligence.

## Files and verification

- `titan/store.py`, `engine.py`: queue, workflow, debate, recovery.
- `providers.py`, `tools.py`, `mcp.py`, `security.py`: guarded calls and permissions.
- `policy.py`, `improvement.py`: evaluation and rollback.
- `server.py`, `web/`: authenticated API and Android-oriented PWA shell with projects, chat, artifacts, schedules and previews. Browser verification is blocked.
- `tests/`: original tests plus platform, API, security, recovery, and browser checks.
- `deploy/`, `Dockerfile`, `compose.yaml`: systemd/TLS and separate API/worker containers. Container builds, startup and scoped isolation tests pass GitHub CI; persistent deployment is not running.
- `docs/evidence/`: captured test results and real offline demonstration.
- `.github/workflows/ci.yml`: CI definition; not executed on GitHub yet.

The original public Python API remains for compatibility, but new work should use the durable queue and CLI. Legacy model calls now use the guarded router. See docs/DEPLOYMENT.md, docs/SECURITY.md, docs/COSTS.md, and NEXT_STEPS.md.

## Demonstrations and benchmarks

```bash
python -m tests.demo_extended
python -m tests.measure
```

Generated demonstration files are under `docs/evidence/`. The integrated demo uses no model fixtures and no external inference. The benchmark numbers describe small local deterministic tasks only.

## Local model support

Set `TITAN_LOCAL_ENABLED=1`, `TITAN_MODEL_LOCAL=<installed-model>` and a loopback `TITAN_LOCAL_URL` exposing OpenAI-compatible chat completions. Non-loopback destinations are refused by this adapter. A model/runtime is not bundled. In Docker, localhost refers to that container; a separate local-model deployment needs a reviewed connection design rather than silently broadening the allowlist.

## Secrets and deployment

Secret variables can use the corresponding `_FILE` variable (for example `GROQ_API_KEY_FILE`). Configure exactly one source. Never commit real `.env` files or secret files. The Docker Compose API reads the operator token from `.secrets/titan_token` and shares a persistent data volume with the worker. See docs/DEPLOYMENT.md before running it. Nothing is deployed by downloading this package.
