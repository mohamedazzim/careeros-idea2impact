# CareerOS AI — Prompt Governance Framework

This document details our prompt engineering, lifecycle testing, and template regression governance policies.

---

## 1. Prompt Versioning & Storage Strategy
To prevent uncontrolled prompt modifications that can lead to behavior drift:
* All prompt templates are extracted from code modules and stored in a central repository, preventing hardcoded string templates.
* Template file naming conventions follow a structured semantic versioning format:
  - Format: `/server/prompts/<agent_name>_v<major>_<minor>.ts`
  - Example: `roadmap_agent_v1_0.ts`

---

## 2. Mandatory Prompt Approvals Flow
Before a new template can be merged into production branches:
1. **Regression Benchmark Analysis**: Run the template against our golden validation dataset (configured in the **AI Evaluation Hub**).
2. **Precision Testing**: The benchmark run must equal or exceed previous scores on key metrics:
   - **Accuracy**: Semantic correctness against ground-truth facts.
   - **Clarity**: Evaluation of formatting and structure.
   - **Completeness**: Evaluates if the prompt followed all instructions.
3. **Approval Register**: SRE teams must review and register the benchmark results before deploying.

---

## 3. Automated Rejection and Rollback Policies
If an active prompt template experiences a sudden drop in output quality or high failure rates in production:

```text
               Production Metrics Poller (AI Evaluation Logs)
                                     │
                                     ▼
                [Symptom: High Hallucination / Parse Fail Check]
                                     │
                                     ▼
                      Is failure rate > 0.5% or Score < 90%?
                                     │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
                     [NO]                        [YES]
             (Maintain Run)          [Automatic System Rollback]
                                     - Revert pointer to Stable vX.X
                                     - Trigger alert notification 
                                     - Increment Fail Log Counters
```

---

## 4. Continuous Evaluation Dashboard
Our SRE teams can monitor actual prompt performance on-demand using the **AI Evaluation Hub**'s prompt matrices. This provides a clear visualization of latency distributions, cache hit parameters, and hallucination risk ratings for every active prompt template.
