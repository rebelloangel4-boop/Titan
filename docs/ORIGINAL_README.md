# TITAN AI — independent multi-model debate MVP

A **working orchestration prototype**, not a 24/7 production agent. Implements six provider adapters, independent proposal generation, cross-model critique, synthesis, and SQLite mission/evaluation persistence.

## Run

Requires Python 3.10+. No third-party Python dependencies.

```bash
export GEMINI_API_KEY='your-key' # set locally, never commit
export GROQ_API_KEY='your-key'
python -m titan.cli 'Design a robust YouTube automation system' --providers gemini,groq
python -m unittest discover -s tests -v
```

Other environment variable names: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`. Model IDs may change: override using `TITAN_MODEL_GEMINI`, `TITAN_MODEL_GROQ`, etc. Provider APIs, free quotas, and model names require live verification before use. The Anthropic adapter uses its native Messages API. This MVP does not automatically load `.env` files.

## Security and reality checks

Never commit API keys. Set account spending limits. Network calls and actual provider inference have **not** been tested without keys. The score `0` denotes *not yet independently evaluated*, not poor quality. This version does not execute arbitrary code, edit GitHub, run unattended, perform live trades, or self-modify. Those require a sandbox, permissions, evaluation harness, durable job runner, and approvals.

## Next milestones

1. GitHub App with repository-scoped access, PR-only changes and audit logs.
2. Durable lease-based workers, retries/backoff, queue and heartbeat for 24/7 missions.
3. Independent benchmark suite; only promote improvements if test results beat baseline.
4. Secure secrets management, rate limits and cost controls.
5. Android PWA and Telegram reporting.
