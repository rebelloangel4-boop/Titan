# Resume TITAN v0.3

1. Recover the latest `titan-core-mvp.zip`, preserving its Git bundle. Read PROJECT_STATUS.md, FEATURE_CHECKLIST.md, TEST_REPORT.md and USER_ACTION_REQUIRED.md.
2. Rerun `python -m unittest discover -s tests -v` (100 tests at this checkpoint); install only the declared development validation dependency if needed. Preserve working behavior.
3. Source is now published to rebelloangel4-boop/Titan with user authorization for public visibility. Inspect and execute CI. Basic browser/container jobs passed; isolation acceptance passed run 41280541414. Expanded browser tests passed run 41280662233. Preserve that coverage. Fix actual failures before claiming readiness.
4. Once two provider credentials exist, verify supported model IDs, free limits and provider-side spending controls, then run a real debate and the frozen model benchmark. Keep transcripts explicitly separate from fixtures.
5. Once a persistent host is authorized, build the image, validate Compose, test the restricted sandbox on a separate appropriate worker, deploy behind TLS, then perform crash/reboot/restore tests.
6. Continue engineering the unfinished domains listed in PROJECT_STATUS.md. Do not present connecting keys/cloud as the only remaining work.
7. Run `python -m tests.demo_extended` to reproduce real local artifacts and `python -m tests.measure` for narrowly scoped performance evidence.
8. Update the checklist based on new evidence, not test count alone. Keep production source modifications reviewed and reversible.

No persistent task is registered that will automatically restart this chat. A deployable worker/scheduler exists in source; it is not a running cloud service.

Independent Gemini audit instructions are in GEMINI_HANDOFF.md. No audit has been received yet.
