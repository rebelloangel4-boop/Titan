# TITAN Phase 1 Backend Foundation — Audit Status

**Branch:** `feat/titan-v2-android-upgrade`  
**Base:** `main` at `ef770e0304d9073a1e1bc73d9cece50ad8be454a`  
**Latest backend implementation commit at this report:** `9b5b908c5b76e44c218fccfb15e4fe92916cca46`  
**Scope:** Backend foundation only. No Android project scaffolded.

## Baseline and verification honesty

- The repository's documented historical checkpoint reported 111 passing `unittest` tests and 23/40 accepted criteria. This is historical evidence, not a fresh baseline.
- The local execution environment could not resolve `github.com`; therefore a local clone, `git status`, local baseline run and local post-change test run were not available.
- The authoritative command remains `python -m unittest discover -s tests -v`.
- Fourteen new unittest cases have been added across SSE, heartbeat, cursor replay, cryptographic signatures, expiry, replay and tamper scenarios.
- GitHub Actions CI is configured to run that command on every push, and the Python job now installs `requirements-api.txt`. The latest observed run is [42788582276](https://github.com/rebelloangel4-boop/Titan/actions/runs/42788582276), still pending with no jobs assigned at the time of this report.
- No test pass is claimed in this report until the latest GitHub Actions run completes successfully.

## Changes committed to the development branch

- `titan/store.py`
  - Added `events_after(cursor, job_id=None, limit=100)`.
  - Validates cursor, job ID and bounded page size.
  - Returns ascending event IDs.
  - Adds composite index `events_job_id_idx ON events(job,id)`, using the existing `events.job` column without a schema-breaking rename.
  - Adds `titan_devices` and `approval_challenges` tables, plus expiry/used index. Existing SQLite WAL and event history are preserved.

- `titan/security.py`
  - Added public-key registration for ECDSA P-256/SHA-256 and Ed25519.
  - Added canonical, domain-separated challenge payload binding device ID, approval ID, stored action digest, expiry and single-use nonce.
  - Added signature verification and atomic challenge consumption / approval transition inside a SQLite write transaction.
  - Supports PEM and base64 DER public keys. Signatures are base64-encoded DER ECDSA or raw Ed25519 bytes.
  - Cryptography is imported lazily; install the API extra for these endpoints.

- `titan/api_services.py`
  - Added shared mission, debate, approval, device and artifact service methods.
  - Reuses the existing Database, Workspace, Router, ToolRegistry and Improvements components.
  - Preserves mission validation and secret redaction.

- `titan/events.py`
  - Added resumable SSE event replay and live tailing.
  - SQLite reads run through `asyncio.to_thread`; polling does not block the ASGI event loop.
  - Uses ascending event IDs, event names, JSON payloads and 15-second heartbeat comments.

- `titan/asgi.py`
  - Added optional authenticated FastAPI adapter.
  - Provides missions, debate lookup, state, approvals, device enrollment, artifact listing/download and SSE endpoints.
  - All synchronous service/database operations in async routes are offloaded using `asyncio.to_thread`.
  - Device enrollment requires both API authentication and `TITAN_DEVICE_ENROLLMENT_TOKEN`.

- `titan/server.py`
  - Reuses the shared API service for mission creation/control, state and artifact reads.
  - Keeps the existing stdlib HTTP server and existing route surface.
  - `POST /api/approve` remains available but now requires the complete device-signed challenge fields; unsigned legacy approvals fail closed with 403.

- `requirements-api.txt`
  - Adds optional FastAPI, Uvicorn, cryptography and HTTPX dependencies. The original backend's stdlib-only runtime remains unchanged unless the ASGI/approval features are used.

- `tests/test_api_sse.py`
  - Covers ascending job-scoped events, cursor reconnect replay, unauthorized SSE access and malformed Last-Event-ID.

- `tests/test_approval_signature.py`
  - Covers successful ECDSA and Ed25519 verification, expired challenge rejection, nonce replay rejection, digest tampering, wrong device and invalid algorithm.

- `.github/workflows/ci.yml`
  - Installs the API extras before running the standard unittest suite.

## Endpoints added to ASGI adapter

- `GET /api/events` — authenticated SSE; accepts `Last-Event-ID` and optional `job_id`.
- `GET /api/missions`, `POST /api/missions`.
- `POST /api/missions/{id}/control`.
- `GET /api/debates/{id}`.
- `GET /api/approvals`.
- `POST /api/devices/register`.
- `POST /api/approvals/{id}/challenge`.
- `POST /api/approvals/{id}/verify`.
- `GET /api/artifacts`, `GET /api/artifacts/{id}`.
- `GET /api/state`, `GET /healthz`.

Run the optional adapter and existing worker as separate processes sharing the same persistent database:
```bash
pip install -r requirements-api.txt
uvicorn titan.asgi:create_app --factory --host 127.0.0.1 --port 8788
python -m titan.cli --worker --db titan.db
```

Set `TITAN_TOKEN` (minimum 32 characters), `TITAN_DB`, and `TITAN_DEVICE_ENROLLMENT_TOKEN` before exposing device enrollment. Deploy behind trusted HTTPS. Do not expose the development ASGI server directly to the public internet.

## Known limitations / follow-up before production

1. The original browser UI's unsigned approve action is intentionally disabled; it needs a device-key challenge/signing UX before it can approve sensitive actions.
2. Device enrollment is protected by a separately configured enrollment secret (minimum 32 characters); production enrollment should add a short-lived, operator-issued enrollment flow and device revocation UI.
3. ECDSA P-256 is the primary Android Keystore-compatible path. Validate the exact Android signature encoding and key attestation policy during Android integration.
4. SSE polling is bounded and non-blocking but is not a push-notification broker; a high event volume may warrant a dedicated notification layer later.
5. FastAPI is an optional transport adapter. Existing stdlib server and worker remain the underlying engine.
6. No Android code, deployment, real provider inference or signed release APK is part of this Phase 1 change.

## Status

**Implementation committed. Test verification pending latest GitHub Actions result.** Do not merge to `main` until the complete existing and new unittest suite passes and the intentional unsigned-approval UI impact is addressed.
