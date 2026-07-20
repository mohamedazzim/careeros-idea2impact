---
title: "Golden Questions And Answers"
document_id: "28_golden_questions_and_answers"
domain: "retrieval"
feature: "golden questions"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - golden-questions
  - retrieval
  - voice
---

# Golden Questions And Answers

## Voice And ElevenLabs Questions

### V000. Explain the full ElevenLabs, Make.com, and Twilio opportunity-call flow.

A high-fit opportunity alert reaches `POST /api/v1/opportunities/alert`, passes through `OpportunityAlertAgent`, `AlertActionService`, `CommunicationOrchestrator`, and `ElevenLabsConversationalOutboundCallService`, then sends a ConvAI outbound-call payload either directly to ElevenLabs or through a webhook bridge that can be Make.com. ElevenLabs ConvAI places the live call through its Twilio-linked phone number and Alex answers from dynamic variables.

### V001. What starts an outbound opportunity voice call?

A frontend or API alert request reaches `POST /api/v1/opportunities/alert`, then `OpportunityAlertAgent`, `CommunicationOrchestrator`, and `ElevenLabsConversationalOutboundCallService.initiate_call`.

### V002. Which provider initiates the active conversational call?

The supported CareerOS voice-agent path is ElevenLabs ConvAI only. A webhook bridge can relay the ConvAI payload, but it is not a separate voice-agent path.

### V003. Does CareerOS call Twilio REST directly for the main opportunity call path?

No. Direct Twilio wrappers exist, but the opportunity voice-agent path is ElevenLabs ConvAI only.

### V004. Which environment variables are required for a real ElevenLabs call?

`ELEVENLABS_CONVAI_AGENT_ID`, `ELEVENLABS_CONVAI_PHONE_NUMBER_ID`, a recipient number, and ConvAI provider access. `PIPEDREAM_WEBHOOK_URL` can only relay the same ConvAI payload.

### V005. What happens in outbound call dry-run mode?

The service returns the ConvAI outbound-call payload with dry-run identifiers and does not call the live provider path.

### V006. How are recipient phone numbers protected?

The resolver normalizes the number, rejects alphabetic input, requires at least ten digits, prefixes `+`, and refuses configured sender/test numbers.

### V007. Where are voice sessions stored?

`VoiceSession`, `VoiceConversation`, and `VoiceOutcome` live in `backend/src/models/jobs.py`.

### V008. Where are ElevenLabs transcripts stored?

`ConversationTranscript` in `backend/src/models/outcome_intelligence.py` stores raw transcript text and speaker turns.

### V009. Is there an inbound ElevenLabs webhook endpoint?

No inbound ElevenLabs callback route was found; transcript handling is polling/on-demand.

### V010. Which service fetches transcripts?

`ConversationRetrievalAgent.retrieve_and_store` fetches ElevenLabs conversation details.

### V011. Which worker retries missing transcripts?

`sync_elevenlabs_transcripts_task` calls `ElevenLabsTranscriptSyncService.scan`.

### V012. What prompt does the repository define for the voice agent?

`voice_opportunity_agent.py` defines Alex, a CareerOS opportunity advisor who answers job questions and asks one question at a time.

### V013. Is that prompt injected into the active outbound call payload?

No. The inspected initiation path passes `prompt=None` and `first_message=None`, so behavior depends on the external ElevenLabs agent configuration plus dynamic variables.

### V014. What job data is passed to ElevenLabs?

Job title, company, description, location, employment type, salary, deadline, application URL, match score, skills, gaps, and resume context.

### V015. What is the Pipedream role in voice?

Pipedream is not a voice agent. If configured, it can only relay the ElevenLabs ConvAI outbound-call payload.

### V016. Is Make.com used for the voice call path?

The repository does not store an exported Make.com voice scenario. However, the runtime can use a webhook bridge for the ElevenLabs ConvAI outbound-call payload. If the configured bridge URL points to a Make.com custom webhook, Make.com relays the payload to ElevenLabs.

### V016a. Where does CareerOS pass the JD to ElevenLabs ConvAI?

CareerOS passes the JD through `conversation_initiation_client_data.dynamic_variables.job_description`, along with role, company, location, salary range, match score, skills, deadline, and application URL.

### V016b. How does CareerOS support Tamil and English opportunity calls?

The backend normalizes Tamil and English language preferences, and the external ElevenLabs agent configuration can enable English and Tamil voices. Dynamic variables are language-neutral, so Alex can answer the same job questions in English, Tamil, or mixed Tamil-English when the ElevenLabs agent is configured for those languages.

### V016c. Does CareerOS use Twilio Say or Play for opportunity calls?

No. The opportunity-call path uses ElevenLabs ConvAI. Twilio is the telephony rail connected to the ElevenLabs phone number ID, not an app-owned static `Say` or `Play` flow.

### V017. What provider error maps to a missing destination number?

HTTP 400 missing destination handling becomes a ConvAI provider payload error.

### V018. How does CareerOS correlate calls after initiation?

It extracts `conversation_id`, `conversationId`, `call_sid`, `callSid`, or `sid` from provider responses.

### V019. Can a call be captured without a conversation ID?

The provider may start a call, but transcript correlation is unreliable without a conversation ID or call SID.

### V020. Which frontend areas can surface opportunity voice actions?

Opportunity and jobs intelligence views contain the related user workflows.

### V021. What table records sync retries?

`ConversationSyncJob` records transcript sync retry and permanent failure state.

### V022. What endpoint returns a stored conversation?

`GET /api/conversations/{conversation_id}` returns session and transcript data.

### V023. What endpoint processes conversation outcomes?

`POST /api/conversations/process` invokes outcome intelligence processing.

### V024. What external configuration is still required?

ElevenLabs ConvAI agent settings and phone-number wiring must be checked outside the repo.

### V025. What is the safest production rollout mode?

Use dry run first, validate the ConvAI payload and recipient selection, then enable the live ConvAI path with provider dashboards open.

### V026. What status should voice be documented as?

Partially implemented: code-backed ConvAI initiation and transcript polling exist, but provider dashboards, inbound webhooks, and prompt injection remain external or missing.

## General CareerOS Questions

### G001. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G002. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G003. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G004. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G005. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G006. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G007. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G008. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G009. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G010. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G011. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G012. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G013. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G014. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G015. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G016. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G017. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G018. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G019. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G020. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G021. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G022. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G023. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G024. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G025. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G026. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G027. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G028. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G029. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G030. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G031. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G032. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G033. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G034. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G035. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G036. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G037. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G038. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G039. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G040. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G041. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G042. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G043. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G044. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G045. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G046. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G047. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G048. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G049. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G050. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G051. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G052. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G053. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G054. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G055. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G056. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G057. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G058. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G059. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G060. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G061. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G062. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G063. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G064. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G065. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G066. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G067. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G068. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G069. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G070. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G071. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G072. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G073. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G074. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G075. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G076. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G077. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G078. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G079. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G080. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G081. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G082. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G083. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G084. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G085. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G086. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G087. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G088. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G089. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G090. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G091. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G092. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G093. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G094. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G095. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G096. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G097. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G098. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G099. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G100. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G101. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G102. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G103. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G104. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G105. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G106. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G107. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G108. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G109. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G110. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G111. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

### G112. What does CareerOS implement for orchestration?

Orchestration and governance exist but include provider-dependent and partially implemented surfaces.

### G113. What does CareerOS implement for authentication?

Authentication is implemented in `backend/src/api/v1/endpoints/auth.py` with strong password checks, token pairs, cookies, and lockout.

### G114. What does CareerOS implement for resume upload?

Resume upload is implemented in `backend/src/api/v1/endpoints/knowledge.py` with PDF/DOCX extraction, validation, chunking, embeddings, and analysis.

### G115. What does CareerOS implement for job refresh?

Job refresh is implemented through `backend/src/services/job_refresh.py` and TheirStack sync.

### G116. What does CareerOS implement for matching?

Matching is deterministic in `backend/src/services/opportunity/job_intelligence_service.py` and combines education, skills, projects, experience, certifications, location, keyword, and semantic evidence.

### G117. What does CareerOS implement for application packages?

Packages are generated in `backend/src/api/v1/endpoints/packages.py` with LLM structured output and deterministic fallback.

### G118. What does CareerOS implement for interview prep?

Interview prep is implemented by `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview`, and frontend interview components.

### G119. What does CareerOS implement for docs RAG?

Docs-RAG is implemented by `backend/src/services/rag/service.py` with Qdrant, NV-Embed, Gemini/DeepSeek, and optional Make.com relay.

### G120. What does CareerOS implement for Qdrant?

Qdrant collections are managed in `backend/src/services/vector_store/qdrant_service.py`; docs use `careeros_rag_docs`.

### G121. What does CareerOS implement for LLM provider?

The LLM factory uses Gemini primary and DeepSeek/NVIDIA fallback.

### G122. What does CareerOS implement for Make.com?

Make.com is present as an optional docs-RAG relay, not as a verified voice workflow.

### G123. What does CareerOS implement for Pipedream?

Pipedream is used as a communication webhook adapter. For voice, it is only a possible relay for the ElevenLabs ConvAI payload, not a voice-agent implementation.

### G124. What does CareerOS implement for TheirStack?

TheirStack is the verified real job provider implementation.

### G125. What does CareerOS implement for learning paths?

Learning and skill-gap workflows are implemented under `backend/src/api/v1/endpoints/learning.py` and `skill_gaps.py`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/api/v1/endpoints/demo_rag.py`
- `docs/rag_v2`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
