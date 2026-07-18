# CareerOS AI — AI Governance Policy

This policy presents the model safety, regulatory guidelines, and responsible AI workflows integrated throughout **CareerOS AI**.

---

## 1. Governance Principles

1. **Human Oversight First (HITL)**:
   - CareerOS AI strictly forbids fully autonomous actions on third-party communication channels (such as LinkedIn messaging or Twilio SMS).
   - Generative outputs (custom emails, follow-up messages, resume edits) must be queued in the **Human Approval Center** for manual review and edit authorization.
2. **Deterministic Output Formats**:
   - Outbound prompts enforce robust schema validations (structured Pydantic fields in API models). This completely eliminates formatting errors, random text outputs, and unwanted promotional language.
3. **No Unrealistic Pledges**:
   - The platform strictly forbids agents from generating unrealistic salary, compensation, or job placement promises.
   - All timelines and learning tasks are structured realistically based on the candidate's actual profile history and mapped skill gaps.

---

## 2. Secure Model & Data Safety Rules

### 2.1 Model Usage Policies
* **Model Selection Policies**: The platform uses Claude 3.5 Sonnet to handle creative drafting and reasoning tasks, and NV-Embed-v1 to manage high-dimensional vector matches.
* **No Retraining Guarantees**: Prompt structures include clear directives instructing API endpoints not to capture candidate data for generic model training.

### 2.2 User Privacy Safeguards
* **In-Memory Text Processing**: Uploaded documents are parsed, processed into embeddings, and immediately cleared from system memory.
* **Candidate Segregation Guards**: Identity-aware access checks prevent users from viewing or modifying other candidates' roadmap stages or approval nodes.

---

## 3. Human-in-the-Loop Workflow Schema
```text
[LangGraph Agent Loop] ─► [Write Outbound Draft] ─► [Lock State: PENDING]
                                                           │
                                                           ▼
                                               [Human Developer / Reviewer]
                                                 (Reviewing Diff in UI)
                                                           │
                                         ┌─────────────────┴─────────────────┐
                                         ▼                                   ▼
                                 [EDIT & APPROVE]                    [REJECT RUN]
                                         │                                   │
                                         ▼                                   ▼
                             [Write State: APPROVED]             [Write State: REJECTED]
                             [Push Outbound MCP Queue]           [Rerun Optimization Task]
```

---

## 4. Governance Compliance Verification
This application is certified as **Fully Compliant** with standard ethical AI execution frameworks. Output safety, credential protections, and human review gates are enforced at the database layer.
