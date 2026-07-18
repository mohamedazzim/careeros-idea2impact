# CareerOS V2 Risk Register

Last verified from source code: 2026-06-19

This register focuses on risks that can realistically affect a V2 rollout of the current CareerOS codebase.

## Risk table

| Risk | Likelihood | Impact | Why it matters | Detection | Mitigation | Related milestone |
|---|---|---|---|---|---|---|
| Provider quota exhaustion | Medium | High | TheirStack, YouTube, LangSmith, or LLM quotas can degrade live behavior | Provider health endpoints, warnings, tests | Circuit breakers, fallback resources, `not_tracked` / degraded labels | M1, M12 |
| Heuristic scores mistaken as truth | High | High | Stars, trust scores, freshness, and match scores can look authoritative even when they are only proxies | Score reviews, evidence audits | Expose formula/evidence/version, show `insufficient_data` when needed | M2, M5, M11 |
| Duplicate communication dispatch | Medium | High | A repeated outbound call or alert can create user harm and wasted provider usage | Lock / dedupe logs, communication request audits | Redis lock, idempotency keys, reuse existing requests | M1, M12, M13 |
| Sparse or missing event history | High | High | Analytics and personalization become misleading without enough events | Metric completeness checks | Add structured events before adding dashboards or predictions | M1, M3, M11 |
| Prompt injection / unsafe retrieval | Medium | High | RAG and copilot features can be manipulated by malformed inputs or embedded secrets | Safety filters, redaction logs | Use strict retrieval, PII redaction, refusal rules, and evidence-only answers | M10, M12 |
| Private repo permission gaps | Medium | Medium | GitHub project validation is weaker without user-authorized private repo access | Provider auth checks | Keep public-search fallback; request explicit permissions only when needed | M6 |
| Seeded fallback mistaken for live discovery | High | Medium | Curated resources are useful, but users may assume they are live verified results | Provider health status | Label seeded fallback clearly; surface provenance in UI | M2, M7 |
| Route prefix regression | Medium | Medium | `/api` vs `/api/v1` mixed routing has historically caused 404s | OpenAPI smoke tests | Keep a route map and endpoint tests for every router family | M0, M13 |
| Default-zero telemetry confusion | High | Medium | Zero values can be read as real metrics even when no telemetry is tracked | UI/QA review | Replace with `not_tracked` or nullable fields | M11 |
| Worker backlog or queue drift | Medium | Medium | Async work can silently lag if workers or queues degrade | Worker health, queue depth, dead letters | Add queue metrics, replay, and fail-fast checks | M1, M13 |
| Missing schema migration order | Medium | High | New analytics or graph tables can break if deployed without the right migration sequence | Migration review | Add migration-first rollout plans, smoke checks, and fallback code paths | M2 through M9 |
| Overconfidence in copilot answers | Medium | High | The copilot can sound confident even when evidence is weak | Golden-question tests, citation checks | Force citations, follow-up questions, and `needs_verification` behavior | M10 |

## Top risks to call out early

### 1. Duplicate dispatch

This is a high-severity risk because the product already touches outbound communication. Any future V2 automation must keep idempotency and lock-based suppression intact.

### 2. Default-zero analytics

This is a product-trust risk. If a dashboard shows zeros where the system really has no telemetry, users will draw false conclusions.

### 3. Quota and provider degradation

This is a platform availability risk. The system already has multiple external dependencies, and V2 must keep working when one of them is limited.

### 4. Copilot hallucination risk

This is an AI trust risk. Evidence-only answers and explicit `insufficient_data` handling are non-negotiable.

## Risk policy for V2

1. Prefer truthful fallback over fabricated confidence.
2. Prefer explicit `not_tracked` / `insufficient_data` labels over default numeric values.
3. Prefer additive schema changes over disruptive rewrites.
4. Prefer evidence citations over free-form explanation when the system is answering about itself.

## Operational acceptance criteria

A V2 milestone is not acceptable unless:

- it has a clear rollback or fallback path
- it has tests or runtime verification
- it does not hide provider failures
- it does not turn missing data into fake certainty
