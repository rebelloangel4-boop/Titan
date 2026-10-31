# Security boundaries and outstanding hardening

Implemented: strong configured API token (minimum 32 characters; generate random), constant-time token comparison, no API CORS, browser origin rejection, request body cap, connection timeout, fixed static path map, restrictive CSP, no HTML insertion of model output, no query-string credentials, no API cache, environment secret redaction, transactional exact-argument approvals, database lease fencing, zero-spend defaults, no host terminal fallback, pinned sandbox-image requirement, no network/container caps when sandbox is enabled.

Limits:

- One trusted operator, not multi-user RBAC. The operator token can approve tools and change routing; models cannot. Do not share it publicly.
- SQLite and env secrets are not encrypted by this application. Use OS permissions and encrypted disks/backups. Memory is untrusted model context, not authority.
- Redaction removes configured secret values and Bearer patterns; it cannot identify all arbitrary private data. Never supply secrets as mission content. Tool results are visible to the authorized operator.
- HTTPS/reverse proxy, credential rotation, rate limiting, host egress controls and stronger deployment protections remain requirements. The API now caps concurrent connections at 32 and failed authentication attempts at 20 per minute per observed client IP. The stdlib server is not a public production perimeter.
- Web/MCP host allowlists, HTTPS-only destinations, public-IP DNS checks and disabled redirects reduce SSRF. The DNS check and connection are separate; DNS rebinding is not fully eliminated. Use only trusted operator-controlled hosts plus enforced outbound firewall/proxy restrictions. Do not allow attacker-controlled domains.
- Docker is not a perfect sandbox against hostile workloads. No runtime was available for acceptance testing. Use a dedicated worker with no secrets, restricted/rootless runtime and patched kernel. Docker daemon access can confer host privilege.
- Approved external calls can finish after pause/cancel. Queue fencing prevents stale results, not remote side effects. Approval consumption before calls intentionally favors manual recovery over unsafe replay.
- External tool credentials are never sent to models by the provided adapters. However an allowlisted MCP server is a separate trust boundary; review its tool permissions and actual behavior.
- The PWA caches only static shell paths. Browser E2E and service-worker behavior have not been verified here due to the missing browser binary.
- Usage ledger is conservative reserved cost, not invoice truth. Free-provider flags are operator assertions; set hard limits at each provider. Prompt/token behavior and actual billing must be verified live.
- Public publishing, financial transactions, trading and destructive production actions are not implemented. Adding a generic MCP tool that can perform these requires careful exact-action approval and account scoping.
- Fixed synthetic benchmarks test routing policy invariants, not security or general intelligence. Production source changes never auto-promote.


v0.3 additions: project-scoped knowledge (one operator, not tenant RBAC); SHA-256 checked artifacts with fixed generated IDs, no-follow reads, a 25 MB per-file cap and aggregate storage quota; exact-argument draft-PR approval restricted to the configured private repository; secret-file source validation; recurring schedule coalescing; scoped benchmark quality; watchdog fencing of late results; child-task cancellation. Browser-facing artifact previews use text nodes or private blob media, never execute downloaded HTML.

The new Docker configuration and sandbox changes have not passed runtime isolation tests. Static review and unit tests cannot certify production security. Database and artifact storage remain plaintext unless the host provides encryption. The web/MCP DNS-to-connect rebinding gap remains a deployment egress-control requirement. Only trusted operator-owned/approved destination hosts should be configured.

The watchdog marks overlong work blocked and prevents stale commits; it does not magically retract an in-flight remote API request. Cancelling a mission can still incur a provider charge already initiated. Generated coding tests may be gamed by generated code and are not an independent acceptance/security oracle. Do not automatically merge those artifacts.
