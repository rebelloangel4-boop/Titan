# Free-tier reality — checked 2026-10-31

| Resource | Official information checked | Implication |
|---|---|---|
| Oracle Always Free A1 | 1,500 OCPU-hours and 9,000 GB-hours monthly, equivalent to 2 OCPU/12 GB; up to 200 GB block storage | Suitable for a small persistent orchestrator if your region has capacity. Idle VMs can be reclaimed. Not an uptime guarantee. |
| GitHub Actions | Current opened allowance page lists $12 included monthly compute usage and 500 MB storage for GitHub Free; search snippets still showed older 2,000-minute wording | Confirm your account billing page. Do not assume the old minute allowance or unlimited private CI. Enable stop-at-budget. |
| Cloudflare Workers Free | 100,000 requests/day; short CPU budgets (10 ms on documented free limit) | Useful for a different edge architecture. Not a persistent Python/SQLite/Docker host. |
| AI inference | Not included with hosting | Each provider/model/account has separate quotas and pricing. No universal free unlimited inference. |
| This local build | No external provider calls made | Local analysis and unit tests require no inference fee. Existing device/cloud electricity, connectivity and account costs still exist. |

Sources:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.github.com/en/billing/reference/product-usage-included
- https://developers.cloudflare.com/workers/platform/limits/
- https://ai.google.dev/gemini-api/docs/openai
- https://console.groq.com/docs/api-reference
- https://platform.claude.com/docs/en/api/messages/create
- https://api-docs.deepseek.com/en/
- https://docs.x.ai/developers/model-capabilities/legacy/chat-completions
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-03-26/basic/transports.mdx

A two-provider debate uses 7 requests, a three-provider debate 10. With the default 50-call daily guard, that is at most 7 complete two-provider debates before other requests/retries consume capacity. Provider token/minute limits can bind sooner. Adding more models increases latency and cost and does not guarantee correctness.

Realistic readiness: local alpha exists now. Once repository access, two keys and a persistent host are available, live smoke tests/deployment still require execution and debugging; a small pilot may take hours, not a guaranteed deadline. A secure general-purpose platform covering all listed domains requires substantial additional implementation and evaluation, not simply more API keys.
