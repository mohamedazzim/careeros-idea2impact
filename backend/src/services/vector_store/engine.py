from typing import List, Dict, Any, Optional
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, ScoredPoint
from src.db.qdrant import get_qdrant
from langsmith import traceable
import logging

logger = logging.getLogger(__name__)

class VectorEngine:
    @traceable(name="vector_db_insert")
    async def insert_vectors(self, collection_name: str, points: List[PointStruct]) -> bool:
        """Inserts vectorized points into a specified Qdrant collection."""
        try:
            qdrant = await get_qdrant()
            await qdrant.upsert(
                collection_name=collection_name,
                points=points
            )
            return True
        except Exception as e:
            logger.error(f"Error inserting vectors to {collection_name}: {e}")
            return False

    def _build_filter(self, filter_kwargs: Optional[Dict[str, Any]] = None) -> Optional[Filter]:
        if not filter_kwargs:
            return None
        conditions = []
        for key, value in filter_kwargs.items():
            if value is not None:
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
        return Filter(must=conditions) if conditions else None

    @traceable(name="vector_db_query")
    async def query_vectors(
        self, 
        collection_name: str, 
        query_vector: List[float], 
        filter_kwargs: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[ScoredPoint]:
        """Queries the vector database applying explicit Exact-Match metadata filters."""
        try:
            qdrant = await get_qdrant()
            
            query_filter = self._build_filter(filter_kwargs)
                
            results = await qdrant.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit
            )
            
            return getattr(results, 'points', [])
        except Exception as e:
            logger.error(f"Error querying vectors from {collection_name}: {e}")
            raise

    # Query Workflows
    @traceable(name="query_resumes")
    async def query_resumes(
        self, 
        query_vector: List[float], 
        user_id: Optional[str] = None,
        resume_id: Optional[int] = None,
        version_num: Optional[int] = None,
        limit: int = 5
    ) -> List[ScoredPoint]:
        filter_kwargs = {
            "user_id": user_id,
            "resume_id": resume_id,
            "version_num": version_num
        }
        # remove None values
        filter_kwargs = {k: v for k, v in filter_kwargs.items() if v is not None}
        return await self.query_vectors("careeros_resumes", query_vector, filter_kwargs, limit)

    @traceable(name="query_jobs")
    async def query_jobs(
        self, 
        query_vector: List[float], 
        company: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: int = 5
    ) -> List[ScoredPoint]:
        filter_kwargs = {
            "company": company,
            "job_id": job_id
        }
        filter_kwargs = {k: v for k, v in filter_kwargs.items() if v is not None}
        return await self.query_vectors("careeros_jobs", query_vector, filter_kwargs, limit)

    @traceable(name="query_knowledge")
    async def query_knowledge(
        self, 
        query_vector: List[float], 
        category: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 5
    ) -> List[ScoredPoint]:
        filter_kwargs = {
            "category": category,
            "source": source
        }
        filter_kwargs = {k: v for k, v in filter_kwargs.items() if v is not None}
        return await self.query_vectors("careeros_knowledge", query_vector, filter_kwargs, limit)

_vector_engine = None


def get_vector_engine() -> VectorEngine:
    global _vector_engine
    if _vector_engine is None:
        _vector_engine = VectorEngine()
    return _vector_engine


def reset_vector_engine() -> None:
    global _vector_engine
    _vector_engine = None


def __getattr__(name: str):
    if name == "vector_engine":
        return get_vector_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
