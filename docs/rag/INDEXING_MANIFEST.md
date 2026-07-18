# Indexing Manifest

Last verified from source code: 2026-06-14

| File | Priority | Chunking rule | Main topics | Metadata |
| --- | --- | --- | --- | --- |
| `docs/rag/README.md` | High | Chunk by section heading | Index, reading order, source-truth rule | `doc_name`, `section`, `priority`, `source_anchor` |
| `docs/rag/architecture.md` | High | One heading block per chunk | System overview, stack, runtime shape | `doc_name`, `section`, `layer`, `source_anchor` |
| `docs/rag/frontend.md` | High | One route or helper section per chunk | Pages, hooks, shell, UI flows | `doc_name`, `route`, `component`, `source_anchor` |
| `docs/rag/backend_apis.md` | High | One router section per chunk | REST and websocket endpoints | `doc_name`, `router`, `endpoint`, `source_anchor` |
| `docs/rag/agents_llms_prompts.md` | High | One agent or prompt family per chunk | Agents, LLMs, prompt registry | `doc_name`, `agent_name`, `prompt_family`, `source_anchor` |
| `docs/rag/workflows.md` | High | One workflow example per chunk | LangGraph flows and end-to-end behavior | `doc_name`, `workflow_name`, `source_anchor` |
| `docs/rag/data_models.md` | Medium | One model group per chunk | ORM models and persistence surfaces | `doc_name`, `model_group`, `table_name`, `source_anchor` |
| `docs/rag/ops_security.md` | High | One topic block per chunk | Auth, security, MCP, observability | `doc_name`, `topic`, `source_anchor` |
| `docs/rag/FEATURE_STATUS.md` | High | One table row per chunk or row groups | Feature readiness and demo notes | `doc_name`, `feature_name`, `status`, `source_anchor` |
| `docs/rag/DEMO_FAQ.md` | High | One FAQ answer per chunk | Mentor/HR questions | `doc_name`, `question`, `answer_type`, `source_anchor` |
| `docs/rag/AGENT_CARDS.md` | High | One agent card per chunk | Core agent responsibilities | `doc_name`, `agent_name`, `source_anchor` |
| `docs/rag/WORKFLOW_EXAMPLES.md` | High | One workflow example per chunk | Step-by-step business flows | `doc_name`, `workflow_name`, `source_anchor` |
| `docs/rag/API_EXAMPLES.md` | High | One endpoint example per chunk | Request/response examples | `doc_name`, `endpoint`, `method`, `source_anchor` |
| `docs/rag/MAKE_RAG_CHATBOT.md` | High | One contract section per chunk | Make scenario, webhook, Qdrant, JSON contract | `doc_name`, `contract_part`, `source_anchor` |
| `docs/rag/KNOWN_LIMITATIONS.md` | Medium | One limitation category per chunk | Gaps, risks, verification points | `doc_name`, `limitation_type`, `source_anchor` |
| `docs/rag/PROJECT_HIGHLIGHTS.md` | Medium | One highlight section per chunk | Reviewer-focused value | `doc_name`, `highlight_type`, `source_anchor` |
| `docs/rag/GOLDEN_QUESTIONS.md` | High | One question row per chunk or batched rows | Test questions and expected answer behavior | `doc_name`, `question`, `expected_source`, `answer_type` |

## Recommended chunking rules

- Keep section headings intact.
- Keep tables together when they fit within a small chunk window.
- Preserve exact file paths and endpoint names.
- Store the latest verified date in metadata.
- Use `source_anchor` values that point to code paths or docs file names.
