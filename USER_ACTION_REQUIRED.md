# TITAN — actions that genuinely need you

Do these in order. You do not need to write code, fix tests, or perform manual video editing. Do not paste passwords or API keys into chat.

## 1. Connect two model providers securely

**Why you:** No provider API keys are configured in this execution environment. Account authentication and acceptance of provider terms must be yours.

**Needed:** Two usable provider accounts and API keys, with supported model IDs. Your requested providers are OpenAI, Gemini, Grok and Claude. Start with two whose API access and acceptable quotas are available to you, then add the others. No paid inference is authorized. A local OpenAI-compatible endpoint is also supported if you already have a capable host and model.

**Cost:** Provider/model dependent. Do not enable paid inference or link a payment method just to bypass a quota without reviewing costs. A ChatGPT subscription is not a TITAN API credential.

**Simplest safe steps:** Tell me which two provider accounts you can use. Once the deployment destination is chosen, enter keys into that host's secret settings or restricted secret files. Send no key values in chat. Keep TITAN_DAILY_USD=0. Confirm actual free quotas before marking a provider free. Provider-side spending limits remain necessary.

**Afterward:** We can execute a genuine independent debate, validate failover and response formats, run the frozen model benchmark, and measure actual latency/usage. More providers can be added after two work.

## 2. Provide an authorized persistent hosting destination

**Why you:** Cloud account verification, terms, identity/payment checks and permissions cannot be completed on your behalf without the account setup. No persistent TITAN service has been created.

**Needed:** Prefer an existing eligible Oracle Always Free VM/account with authorized access. A Render account is connected, but repository access and a reviewed durable-storage/worker plan are still required; no paid service has been created. A Linux host you already control is another option.

**Cost:** ₹0 only if the selected resources are actually covered by your account's free allowance. Capacity and account eligibility may block the free option. A VM or database outside that allowance can charge money. Do not enable paid fallback automatically.

**Simplest safe steps:** Tell me whether you have an Oracle account and an existing free VM, or another Linux host. Share resource identifiers, not private SSH keys/passwords. Use a supported secure connection/secret mechanism for host access. If you prefer Render, confirm the intended workspace and review any proposed charge before creation.

**Afterward:** Docker build and sandbox acceptance tests already pass CI. With authorized hosting I can perform HTTPS deployment, persistent worker configuration, host restart/off-host restore tests and Android PWA verification. The prepared deployment package alone does not start a service.

## 3. Optional service connections, after the core works

**Why you:** These connect your private files, recipients or market-data account. Permissions and recipient selection must be explicit.

- **Google Drive:** Authorize the particular account and file scope. The current connector accepts an access token; refresh-token renewal is implemented and fixture-tested; initial consent and live verification remain. It is not enough to connect Drive to ChatGPT and assume standalone TITAN inherits it.
- **Telegram:** Create/select your bot and confirm the exact destination chat. Store its token securely. The connector requires exact approval for each send; no notifications have been sent during development.
- **Browser/MCP:** Select the trusted server and allowlisted tools. The current JSON HTTP adapter targets MCP 2025-03-26; verify server compatibility. Sensitive actions remain approval-gated.
- **Indian market data:** Select a legally accessible data source and authorize any account needed. Confirm whether it has fees. Current paper tests use supplied sample prices, not live NSE/institutional data; live trading is disabled and not part of setup.
- **Natural voices/animation:** Select an available local model/runtime or licensed provider and its budget. Current local video output is a title-card MP4 with synthetic tone audio, not finished AI HOUSE production.

**Afterward:** We can test each integration separately and establish its real limits. These connections do not automatically complete the remaining engineering work listed in PROJECT_STATUS.md.
