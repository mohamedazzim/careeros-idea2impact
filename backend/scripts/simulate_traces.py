import time
import os
import uuid
from src.observability import (
    tracer, structured_logger,
    request_id_ctx, user_id_ctx, workflow_id_ctx,
    RETRIEVAL_LATENCY_HIST, QDRANT_LATENCY_HIST, RERANK_LATENCY_HIST,
    LLM_TOKEN_USAGE, LLM_LATENCY_HIST,
    AGENT_NODE_LATENCY_HIST, AGENT_RETRIES, AGENT_CHECKPOINTS,
    MCP_INVOCATION_COUNT, MCP_LATENCY_HIST
)
from langsmith import traceable

# 1. Resume Pipeline
@traceable(name="resume_pipeline")
def run_resume_pipeline():
    with tracer.start_as_current_span("resume_pipeline") as span:
        workflow_id_ctx.set(f"wf_{uuid.uuid4().hex[:8]}")
        start = time.time()
        
        with tracer.start_as_current_span("pii_filtering"):
            structured_logger.info("PII filtering started")
            time.sleep(0.05)
            
        with tracer.start_as_current_span("chunking"):
            structured_logger.info("Chunking started")
            time.sleep(0.03)
            
        with tracer.start_as_current_span("embedding"):
            structured_logger.info("Embedding started")
            time.sleep(0.1)
            LLM_LATENCY_HIST.labels(model="text-embedding-3-small", operation="embed").observe(0.1)
            LLM_TOKEN_USAGE.labels(model="text-embedding-3-small", token_type="prompt").inc(500)
            
        with tracer.start_as_current_span("qdrant_indexing"):
            structured_logger.info("Qdrant indexing started")
            time.sleep(0.08)
            QDRANT_LATENCY_HIST.observe(0.08)

        span.set_attribute("resume_id", "RES123")
        span.set_attribute("latency_ms", (time.time() - start) * 1000)

# 2. Retrieval Pipeline
@traceable(name="retrieval_pipeline")
def run_retrieval_pipeline():
    with tracer.start_as_current_span("retrieval_pipeline") as span:
        start = time.time()
        
        with tracer.start_as_current_span("query_embedding"):
            structured_logger.info("Query embedding")
            time.sleep(0.02)
            
        with tracer.start_as_current_span("qdrant_search"):
            structured_logger.info("Qdrant search")
            time.sleep(0.04)
            QDRANT_LATENCY_HIST.observe(0.04)
            
        with tracer.start_as_current_span("reranking"):
            structured_logger.info("Reranking")
            time.sleep(0.06)
            RERANK_LATENCY_HIST.observe(0.06)
            
        dur = time.time() - start
        RETRIEVAL_LATENCY_HIST.labels(operation="search").observe(dur)
        span.set_attribute("latency_ms", dur * 1000)
        span.set_attribute("results_count", 5)

# 3. Agent Trace
@traceable(name="agent_pipeline")
def run_agent_pipeline():
    with tracer.start_as_current_span("agent_pipeline") as span:
        start = time.time()
        
        for node in ["resume_agent", "scoring_agent", "recommendation_agent", "reporting_agent", "opportunity_agent"]:
            with tracer.start_as_current_span(f"node_{node}") as node_span:
                ns = time.time()
                structured_logger.info(f"Agent Node {node} executing")
                time.sleep(0.05)
                
                if node == "scoring_agent":
                    LLM_LATENCY_HIST.labels(model="claude-4-6-sonnet", operation="generate").observe(0.2)
                    LLM_TOKEN_USAGE.labels(model="claude-4-6-sonnet", token_type="total").inc(1500)
                    time.sleep(0.2)
                
                # simulate occasionally hitting a retry
                if node == "recommendation_agent":
                    AGENT_RETRIES.labels(node=node).inc()
                    structured_logger.warning(f"Agent Node {node} retried")
                
                dur = time.time() - ns
                AGENT_NODE_LATENCY_HIST.labels(node=node).observe(dur)
                AGENT_CHECKPOINTS.labels(node=node).inc()
                node_span.set_attribute("latency_ms", dur * 1000)
                
        span.set_attribute("latency_ms", (time.time() - start) * 1000)

# 4. MCP Trace
@traceable(name="mcp_pipeline")
def run_mcp_pipeline():
    with tracer.start_as_current_span("mcp_pipeline") as span:
        start = time.time()
        
        with tracer.start_as_current_span("threshold_evaluation"):
            structured_logger.info("Evaluating thresholds")
            time.sleep(0.01)
            
        with tracer.start_as_current_span("mcp_elevenlabs"):
            structured_logger.info("Invoking ElevenLabs MCP")
            time.sleep(0.3)
            MCP_INVOCATION_COUNT.labels(tool="elevenlabs:generate_audio").inc()
            MCP_LATENCY_HIST.labels(tool="elevenlabs:generate_audio").observe(0.3)
            
        with tracer.start_as_current_span("mcp_twilio"):
            structured_logger.info("Invoking Twilio MCP")
            time.sleep(0.2)
            MCP_INVOCATION_COUNT.labels(tool="twilio:make_call").inc()
            MCP_LATENCY_HIST.labels(tool="twilio:make_call").observe(0.2)
            
        span.set_attribute("latency_ms", (time.time() - start) * 1000)

# 5. Distributed Trace (E2E)
@traceable(name="distributed_e2e_request")
def run_distributed_trace():
    req_id = str(uuid.uuid4())
    request_id_ctx.set(req_id)
    user_id_ctx.set("user_xyz_99")
    
    with tracer.start_as_current_span("http_post_evaluate") as span:
        span.set_attribute("request_id", req_id)
        structured_logger.info("Received End-to-End Request")
        
        run_resume_pipeline()
        run_retrieval_pipeline()
        run_agent_pipeline()
        run_mcp_pipeline()
        
        structured_logger.info("End-to-End Request Completed")
        span.set_attribute("http.status_code", 200)

if __name__ == "__main__":
    os.environ["OTEL_EXPORTER"] = "console"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "CareerOS_Observability_Validations"
    print("--- 🚀 Generating Distributed Traces & Metrics ---")
    run_distributed_trace()
    print("--- ✅ Trace generation complete ---")
