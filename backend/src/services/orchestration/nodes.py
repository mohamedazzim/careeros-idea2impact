import logging
import time

from src.schemas.orchestration import CareerOSState
from src.services.retrieval.orchestrator import retrieval_orchestrator
from src.services.evaluation.evaluation_engine import get_evaluation_engine as evaluation_engine
from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)

@trace_async("resume_agent")
async def resume_agent(state: CareerOSState) -> CareerOSState:
    """Resume Agent: Retrieves resume + job context via semantic search over Qdrant."""
    start_time = time.time()

    if "execution_metrics" not in state or not state["execution_metrics"]:
        state["execution_metrics"] = {}
    if "errors" not in state or not state["errors"]:
        state["errors"] = []
    if "retries" not in state:
        state["retries"] = {}

    try:
        resume_id = state.get("resume_id", "")
        job_id = state.get("job_id", "")
        user_id = state.get("user_id", "unknown")

        # ── Retrieve resume chunks from Qdrant via semantic search ──
        query = state.get("query") or f"resume_id:{resume_id}"
        retrieval_res = await retrieval_orchestrator.retrieve_context(
            query=query,
            collection_type="resumes",
            filter_kwargs={"user_id": user_id} if user_id != "unknown" else None,
            top_k=5,
            top_n=3,
        )
        state["retrieved_context"] = retrieval_res.context
        state["retrieved_chunks"] = [
            c.model_dump() for c in retrieval_res.retrieved_chunks
        ]
        state["citations"] = [
            c.model_dump() for c in retrieval_res.citations
        ]

        # ── Build resume data from retrieved chunks ──
        resume_text_parts = []
        resume_skills = set()
        for chunk in retrieval_res.retrieved_chunks:
            resume_text_parts.append(chunk.text)
            meta = chunk.metadata or {}
            for skill in meta.get("skills", []):
                resume_skills.add(skill)

        resume_text = "\n\n".join(resume_text_parts) if resume_text_parts else state.get("resume_data", {}).get("text", "")
        state["resume_data"] = {
            "text": resume_text,
            "skills": list(resume_skills),
            "chunks": [{"text": c.text, "section": (c.metadata or {}).get("section", "")} for c in retrieval_res.retrieved_chunks],
        }

        # ── Retrieve job context if a job_id is provided ──
        if job_id and job_id != "default_job":
            job_query = state.get("job_query") or f"job_id:{job_id}"
            job_retrieval = await retrieval_orchestrator.retrieve_context(
                query=job_query,
                collection_type="jobs",
                filter_kwargs={"job_id": job_id},
                top_k=3,
                top_n=1,
            )
            state["job_data"] = {
                "text": job_retrieval.context,
                "title": (job_retrieval.retrieved_chunks[0].metadata or {}).get("title", "") if job_retrieval.retrieved_chunks else "",
                "company": (job_retrieval.retrieved_chunks[0].metadata or {}).get("company", "") if job_retrieval.retrieved_chunks else "",
            }
        else:
            state["job_data"] = state.get("job_data") or {"text": ""}

    except Exception as e:
        logger.error(f"Resume agent failed: {e}")
        state["errors"].append(f"Resume Agent Error: {str(e)}")

    state["execution_metrics"]["resume_agent_latency"] = time.time() - start_time
    return state

@trace_async("scoring_agent")
async def scoring_agent(state: CareerOSState) -> CareerOSState:
    """
    Scoring Agent: Uses the Claude evaluation engine to score the resume vs job context.
    """
    start_time = time.time()
    try:
        if state.get("errors"):
            return state

        resume_text = state.get("resume_data", {}).get("text", "")
        job_text = state.get("job_data", {}).get("text", "")
        context = state.get("retrieved_context", "")

        eval_res = await evaluation_engine.evaluate(
            resume_text=resume_text,
            job_text=job_text,
            context=context
        )
        
        state["evaluation_result"] = eval_res["evaluation"]
    except Exception as e:
        logger.error(f"Scoring agent failed: {e}")
        state["errors"].append(f"Scoring Agent Error: {str(e)}")
        
    state["execution_metrics"]["scoring_agent_latency"] = time.time() - start_time
    return state


@trace_async("recommendation_agent")
async def recommendation_agent(state: CareerOSState) -> CareerOSState:
    """
    Recommendation Agent: Extracts the actionable recommendations from evaluation.
    """
    start_time = time.time()
    try:
        if state.get("errors"):
            return state

        eval_res = state.get("evaluation_result", {})
        recommendations = eval_res.get("recommendations", [])
        
        # Sort or prioritize recommendations here if needed
        state["recommendations"] = recommendations
    except Exception as e:
        logger.error(f"Recommendation agent failed: {e}")
        state["errors"].append(f"Recommendation Agent Error: {str(e)}")
        
    state["execution_metrics"]["recommendation_agent_latency"] = time.time() - start_time
    return state

@trace_async("reporting_agent")
async def reporting_agent(state: CareerOSState) -> CareerOSState:
    """
    Reporting Agent: Compiles final JSON report.
    """
    start_time = time.time()
    try:
        if state.get("errors"):
            return state

        report = {
            "user_id": state.get("user_id"),
            "resume_id": state.get("resume_id"),
            "job_id": state.get("job_id"),
            "evaluation": state.get("evaluation_result"),
            "prioritized_recommendations": state.get("recommendations"),
            "status": "completed"
        }
        state["report"] = report
    except Exception as e:
        logger.error(f"Reporting agent failed: {e}")
        state["errors"].append(f"Reporting Agent Error: {str(e)}")
        
    state["execution_metrics"]["reporting_agent_latency"] = time.time() - start_time
    return state

@trace_async("opportunity_agent")
async def opportunity_agent(state: CareerOSState) -> CareerOSState:
    """
    Opportunity Agent: Decides if this match warrants an opportunity alert.
    """
    start_time = time.time()
    try:
        if state.get("errors"):
            return state

        match_score = state.get("evaluation_result", {}).get("match_score", {}).get("score", 0)
        ats_score = state.get("evaluation_result", {}).get("ats_score", {}).get("score", 0)
        
        # Pull deadline from job_data or default to 5 for mock logic
        deadline_days = state.get("job_data", {}).get("deadline_days", 5) 
        
        # 1. Threshold Evaluation
        if (match_score >= 85 or ats_score >= 85) and deadline_days <= 7:
            state["opportunity_alert"] = True
            
            # Execute MCP Workflow natively here for simplicity or via tools
            try:
                from src.services.mcp_client import execute_mcp_opportunity_workflow
                # Candidate name and job title should come from state, mock for safety
                candidate_name = state.get("resume_data", {}).get("name", "Candidate")
                job_title = state.get("job_data", {}).get("title", "Target Role")
                company = state.get("job_data", {}).get("company", "Target Company")
                phone_number = state.get("resume_data", {}).get("phone", "+15555555555")
                
                mcp_result = await execute_mcp_opportunity_workflow(
                    candidate_name=candidate_name,
                    job_title=job_title,
                    company=company,
                    match_score=match_score,
                    urgency="High (Deadline approaching)",
                    phone_number=phone_number
                )
                state.setdefault("metadata", {})["mcp_results"] = mcp_result
            except Exception as mcp_err:
                logger.error(f"MCP Workflow failed: {mcp_err}")
                state["errors"].append(f"MCP Execution Error: {mcp_err}")
        else:
            state["opportunity_alert"] = False
            
    except Exception as e:
        logger.error(f"Opportunity agent failed: {e}")
        state["errors"].append(f"Opportunity Agent Error: {str(e)}")
        
    state["execution_metrics"]["opportunity_agent_latency"] = time.time() - start_time
    return state

# Fallback/Recovery nodes
@trace_async("recovery_agent")
async def recovery_agent(state: CareerOSState) -> CareerOSState:
    """Graceful recovery handling state."""
    logger.info("Running recovery path...")
    state.setdefault("metadata", {})["status"] = "failed_with_recovery"
    return state
