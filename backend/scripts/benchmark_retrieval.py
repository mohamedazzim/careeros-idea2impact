import asyncio
import time
import os
import sys

# Add backend dir to sys path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.retrieval.orchestrator import retrieval_orchestrator
from src.schemas.retrieval import RetrievedChunk
from src.services.vector_store.engine import vector_engine
from qdrant_client.models import PointStruct

async def setup_mock_data():
    # Insert some dummy generic vectors into resumes to benchmark
    points = []
    import random
    for i in range(100):
        vec = [random.random() for _ in range(4096)]
        payload = {"text": f"Bench chunk {i}", "source": "Benchmark"}
        points.append(PointStruct(id=i+1000, vector=vec, payload=payload))
        
    await vector_engine.insert_vectors("careeros_resumes", points)

async def run_benchmark():
    os.environ["MOCK_EMBEDDINGS"] = "true"
    os.environ["MOCK_RERANKER"] = "true"
    
    print("Setting up mock benchmark data...")
    await setup_mock_data()
    
    print("\n--- Running Small Query Benchmark (top_k=10, top_n=5) ---")
    start_time = time.time()
    result = await retrieval_orchestrator.retrieve_context("Test small query", top_k=10, top_n=5)
    total_time = time.time() - start_time
    
    print(f"Total Latency: {result.metrics['total_latency'] * 1000:.2f}ms")
    print(f"  Embed Latency: {result.metrics['embed_latency'] * 1000:.2f}ms")
    print(f"  Retrieval Latency: {result.metrics['retrieval_latency'] * 1000:.2f}ms")
    print(f"  Rerank Latency: {result.metrics['rerank_latency'] * 1000:.2f}ms")
    print(f"  Assembly Latency: {result.metrics['assembly_latency'] * 1000:.2f}ms")
    print(f"Retrieved: {len(result.retrieved_chunks)}, Reranked: {len(result.reranked_chunks)}")
    print(f"Citations: {len(result.citations)}")
    
    # Very basic pseudo Recall computation
    pseudo_recall = len(result.retrieved_chunks) / 10 if len(result.retrieved_chunks) <= 10 else 1.0
    pseudo_precision = len(result.reranked_chunks) / 5 if len(result.reranked_chunks) <= 5 else 1.0
    print(f"Mock Recall@10: {pseudo_recall * 100:.2f}%")
    print(f"Mock Precision@5: {pseudo_precision * 100:.2f}%")
    
    print("\n--- Running Large Query Benchmark (top_k=50, top_n=10) ---")
    result = await retrieval_orchestrator.retrieve_context("Test large query", top_k=50, top_n=10)
    print(f"Total Latency: {result.metrics['total_latency'] * 1000:.2f}ms")
    print(f"  Embed Latency: {result.metrics['embed_latency'] * 1000:.2f}ms")
    print(f"  Retrieval Latency: {result.metrics['retrieval_latency'] * 1000:.2f}ms")
    print(f"  Rerank Latency: {result.metrics['rerank_latency'] * 1000:.2f}ms")
    print(f"  Assembly Latency: {result.metrics['assembly_latency'] * 1000:.2f}ms")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
