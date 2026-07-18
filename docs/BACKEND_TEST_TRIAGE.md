# Backend Test Triage

Last verified from source code: 2026-07-18

This file records the backend publication gate outcome and the test fixes made to avoid false negatives from provider-backed or stale contract assumptions.

## Current Backend Gate

| Gate | Result |
|---|---|
| Test collection | 1088 collected |
| Full suite | 1040 passed, 48 skipped, 0 failed |
| Integration marker | 1 passed, 14 skipped, 1073 deselected, 0 failed |
| Warning count | 207 warnings in the full suite |
| Schema head | `033_schema_contract_alignment` |
| Fresh migration | Passed |
| Alembic check | Passed; 0 detected upgrade operations |

## Resolved Test Corrections

| Area | Cause | Resolution | Production Impact |
|---|---|---|---|
| Security rate limiting | Test could observe live Redis state when a local stack was running. | Isolated the rate-limit test from real Redis detection. | None; test isolation only. |
| Agent scoring | A scoring test could call a live LLM path. | Limited provider use in tests with explicit mocks. | None; prevents unintended provider calls during tests. |
| Retrieval fallback | Provider keys from local environment changed expected fallback behavior. | Split provider-selection and fallback assertions so each path is explicit. | None; improves deterministic tests. |
| TheirStack slots | Tests expected stale default query limits. | Aligned assertions with configured search limits. | None; test-contract correction only. |
| Schema drift | Alembic template and metadata comparison reported unresolved drift. | Added `033_schema_contract_alignment`, model nullability fixes, and narrow Alembic comparison filters for documented representation-only differences. | Positive; fresh migration and metadata checks now pass. |

## Remaining Watch Items

| Area | Status | Notes |
|---|---|---|
| Provider integration tests | Skipped unless external credentials/services are configured. | This is expected for public repository validation. |
| Frontend browser E2E | Not part of backend gate. | Covered separately by the synthetic Docker golden path and frontend Vitest smoke coverage. |
| Dependency warnings | Present but non-failing. | Track warnings during dependency upgrades; do not suppress real application errors. |
