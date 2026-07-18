# CareerOS AI — Agent Governance Policy

This framework details the allowed actions, failure containment rules, and boundaries enforced on all autonomous agents within **CareerOS AI**.

---

## 1. Enforced Action Boundaries

| Agent Persona | Allowed Actions | Strictly Restricted Actions |
|---|---|---|
| **Roadmap Agent** | Analyze candidate experience and design multi-stage educational plans. | Assign precise salary guarantees or make job placement promises. |
| **Outbound Agent** | Coordinate recommendations, compose custom emails, and draft follow-ups. | Automatically send unsolicited materials, execute API actions without human review, or send spam. |
| **RAG Retrieval Agent**| Scan knowledge documents and extract semantic match data. | Access database profiles or modify security credentials of other tenants. |

---

## 2. Failure Containment Protocols (Circuit Breaker Protection)
To protect system reliability if an agent experiences connection errors, timeouts, or API rate limits, the platform isolates the execution path:
* **Failure Threshold Limits**: If an agent node triggers **3 consecutive failures**, the circuit breaker trips from `CLOSED` to `OPEN`.
* **Graceful Degradation Queues**: Instead of returning raw exceptions to the client, failing payloads are stored in the `DegradationQueue`.
* **State Recovery Rules**: In `OPEN` status, requests are held until a **6,000ms cool-down period** expires. The circuit then enters `HALF_OPEN` to test downstream system health.

---

## 3. Human Review Requirements
To ensure safety and quality control:
* Generative actions (like custom draft emails or outbound messages) must be saved with a `PENDING` state in the database.
* Reviewers can examine the AI-generated copy, make manual edits, and approve or reject the message before it is sent to outbound queues.

---

## 4. System Integrity Certification
All active agent configurations have been audited, tested, and certified for enterprise production use. Each step in the agent execution paths writes trace logs to ensure full SRE observability.
