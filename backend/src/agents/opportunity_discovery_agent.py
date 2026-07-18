"""Phase 5 — Opportunity Discovery Agent.

Discovers matching opportunities by retrieving candidate context from Qdrant
and evaluating against market signals.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.core.config import settings
from src.agents.agent_observability import get_agent_observability

@dataclass
class DiscoveryState:
    discovery_run_id: str
    user_id: str
    candidate_context: Dict[str, Any] = field(default_factory=dict)
    resume_context: Dict[str, Any] = field(default_factory=dict)
    market_context: Dict[str, Any] = field(default_factory=dict)
    discovered_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class OpportunityDiscoveryAgent:
    AGENT_NAME = "opportunity_discovery"

    def __init__(self):
        self.observability = get_agent_observability()

    async def discover(
        self,
        user_id: str,
        candidate_context: Optional[Dict[str, Any]] = None,
        session_uid: str = "",
    ) -> DiscoveryState:
        t0 = time.time()
        run_id = str(uuid.uuid4())
        state = DiscoveryState(
            discovery_run_id=run_id,
            user_id=user_id,
            candidate_context=candidate_context or {},
        )

        try:
            state.resume_context = await self._retrieve_resume_context(user_id)
            state.market_context = await self._retrieve_market_signals(user_id, state.resume_context, state.candidate_context)
            state.discovered_opportunities = await self._evaluate_opportunities(state)

            state.reasoning_chain.append(
                f"Retrieved resume context with {len(state.resume_context)} fields"
            )
            state.reasoning_chain.append(
                f"Market signals: {len(state.market_context.get('opportunities', []))} opportunities found"
            )
            state.reasoning_chain.append(
                f"Discovered {len(state.discovered_opportunities)} matching opportunities"
            )

            state.confidence = self._compute_confidence(state)
            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        self.observability.record_confidence(self.AGENT_NAME, state.confidence)
        return state

    async def _retrieve_resume_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieve candidate resume context from Qdrant via semantic vector search."""
        try:
            from src.services.vector_store.qdrant_service import get_qdrant_service
            from src.services.embedding.embedding_service import get_embedding_service

            qdrant_svc = get_qdrant_service()
            embed_svc = get_embedding_service()

            candidate_query = f"skills experience education for user {user_id}"
            query_vector = await embed_svc.embed_query(candidate_query)

            # Try careeros_resumes first, then careeros_knowledge without user_id filter
            results = await qdrant_svc.search(
                collection_name="careeros_resumes",
                query_vector=query_vector,
                filter_kwargs={"user_id": user_id} if user_id != "unknown" else None,
                limit=50,
                score_threshold=0.3,
            )

            if not results:
                results = await qdrant_svc.search(
                    collection_name="careeros_knowledge",
                    query_vector=query_vector,
                    filter_kwargs=None,  # knowledge items don't have user_id
                    limit=50,
                    score_threshold=0.3,
                )

            # Always enrich with DB resume chunks if user has them
            db_chunks = await self._retrieve_resume_from_db(user_id)
            if db_chunks:
                if not results:
                    results = db_chunks
                else:
                    results = list(results) + db_chunks

            if not results:
                return {
                    "user_id": user_id,
                    "status": "no_resume_found",
                    "skills": [],
                    "experience_years": 0,
                    "resume_chunks": [],
                }

            all_skills = set()
            total_years = 0.0
            chunks = []
            seen_titles = set()

            # Known skill keywords for extraction from text
            KNOWN_SKILLS = {
                "python", "javascript", "typescript", "java", "go", "golang", "rust", "c++", "c#",
                "react", "angular", "vue", "node", "nextjs", "django", "flask", "fastapi",
                "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
                "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
                "graphql", "rest", "grpc", "sql", "nosql", "linux", "git", "ci/cd",
                "machine learning", "data", "tensorflow", "pytorch", "spark", "hadoop",
                "css", "html", "sass", "tailwind",
            }

            for rec in results:
                payload = rec.payload or {}
                text = payload.get("text", "")
                chunks.append({
                    "text": text[:500],
                    "section": payload.get("section", payload.get("category", "")),
                    "chunk_index": payload.get("chunk_index", 0),
                    "score": rec.score,
                })
                # Extract skills from text
                text_lower = text.lower()
                for skill in KNOWN_SKILLS:
                    if skill in text_lower:
                        all_skills.add(skill)
                # Also check dedicated skills field
                skills = payload.get("skills", [])
                if isinstance(skills, list):
                    all_skills.update(skills)
                elif isinstance(skills, str):
                    all_skills.update(s.strip() for s in skills.split(",") if s.strip())
                # Extract experience from resume text
                import re
                years_match = re.findall(r'(\d+)[\+]?\s*(?:years|yrs)', text, re.IGNORECASE)
                for y in years_match:
                    try:
                        total_years = max(total_years, float(y))
                    except ValueError:
                        pass
                title = payload.get("title", "")
                if title:
                    seen_titles.add(title)

            resume_text = " ".join(c.get("text", "") for c in chunks[:20])
            return {
                "user_id": user_id,
                "status": "retrieved",
                "skills": sorted(all_skills),
                "experience_years": total_years,
                "resume_chunks": chunks,
                "titles": sorted(seen_titles),
                "chunk_count": len(chunks),
                "resume_text": resume_text,
            }
        except Exception as exc:
            return {
                "user_id": user_id,
                "status": "retrieval_failed",
                "skills": [],
                "experience_years": 0,
                "error": str(exc),
            }

    async def _retrieve_resume_from_db(self, user_id: str) -> list:
        """Fallback: load resume chunks from PostgreSQL when Qdrant returns empty."""
        try:
            from src.db.session import async_session
            from sqlalchemy import text
            async with async_session() as db:
                result = await db.execute(text(
                    "SELECT rc.content, rc.chunk_index, rc.metadata "
                    "FROM resume_chunks rc "
                    "JOIN resume_versions rv ON rc.version_id = rv.id "
                    "JOIN resumes r ON rv.resume_id = r.id "
                    "WHERE r.user_id = :uid AND rc.deleted_at IS NULL "
                    "ORDER BY rc.chunk_index LIMIT 50"
                ), {"uid": user_id})
                rows = result.fetchall()
                if not rows:
                    return []
                chunks = []
                for row in rows:
                    meta = row[2] or {}
                    if isinstance(meta, str):
                        import json as _json
                        try:
                            meta = _json.loads(meta)
                        except Exception:
                            meta = {}
                    payload = {
                        "text": row[0],
                        "chunk_index": row[1],
                        "section": meta.get("section", meta.get("category", "")),
                        "skills": meta.get("skills", []),
                    }
                    chunks.append(type("QdrantHit", (), {"payload": payload, "score": 0.8})())
                return chunks
        except Exception as e:
            logger.warning(f"DB resume fallback failed for user {user_id}: {e}")
            return []

    async def _retrieve_market_signals(
        self, user_id: str, resume_context: Dict[str, Any], candidate_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve market signals: relevant job postings from Qdrant via semantic search."""
        try:
            from src.services.vector_store.qdrant_service import get_qdrant_service
            from src.services.embedding.embedding_service import get_embedding_service
            from src.services.opportunity.market_signal_engine import get_market_signal_engine
            from src.db.session import async_session
            from src.db.repositories.domain_repositories import JobRepository

            qdrant_svc = get_qdrant_service()
            embed_svc = get_embedding_service()

            skills = resume_context.get("skills", []) or candidate_context.get("skills", [])
            titles = resume_context.get("titles", []) or candidate_context.get("titles", [])

            skill_str = " ".join(skills[:10]) if skills else "software engineer"
            title_str = " ".join(titles[:3]) if titles else ""
            market_query = f"job openings matching {skill_str} {title_str}"
            query_vector = await embed_svc.embed_query(market_query)

            results = await qdrant_svc.search(
                collection_name="careeros_jobs",
                query_vector=query_vector,
                limit=50,
                score_threshold=0.1,
            )

            if not results:
                # Fallback: search careeros_knowledge for job-like knowledge entries
                results = await qdrant_svc.search(
                    collection_name="careeros_knowledge",
                    query_vector=query_vector,
                    limit=30,
                    score_threshold=0.1,
                )

            opportunities = []
            for rec in results:
                payload = rec.payload or {}
                if not payload.get("source_url"):
                    continue
                opp = {
                    "id": payload.get("job_id", str(uuid.uuid4())),
                    "source_job_id": payload.get("source_job_id", payload.get("job_uid", payload.get("job_id", ""))),
                    "title": payload.get("title", ""),
                    "company": payload.get("company", ""),
                    "text": payload.get("text", "")[:1000],
                    "skills": payload.get("skills", []),
                    "source": payload.get("source", "qdrant"),
                    "source_url": payload.get("source_url", ""),
                    "ingested_at": payload.get("ingested_at", ""),
                    "relevance_score": rec.score,
                }
                opportunities.append(opp)

            if not opportunities:
                async with async_session() as db:
                    repo = JobRepository(db)
                    jobs = await repo.find_active(limit=500)
                    for job in jobs:
                        if not job.source_url:
                            continue
                        opp = {
                            "id": str(job.id),
                            "source_job_id": job.source_job_id or job.job_uid,
                            "title": job.title,
                            "company": job.company or "",
                            "text": job.description or "",
                            "skills": job.skills_required or [],
                            "source": job.source or "provider",
                            "source_url": job.source_url,
                            "ingested_at": job.ingested_at.isoformat() if job.ingested_at else "",
                            "relevance_score": 1.0,
                        }
                        opportunities.append(opp)

            # Enrich with market signals
            engine = get_market_signal_engine()
            for opp in opportunities:
                opp["market_demand_score"] = engine.market_demand_score(opp)
                opp["market_signals"] = engine.get_signals(
                    role=opp.get("title", ""), domain=opp.get("text", "")
                )

            return {
                "opportunities": opportunities,
                "market_trends": engine._base_signals(),
                "timestamp": time.time(),
            }
        except Exception as exc:
            return {
                "opportunities": [],
                "market_trends": {},
                "timestamp": time.time(),
                "error": str(exc),
            }

    async def _evaluate_opportunities(self, state: DiscoveryState) -> List[Dict[str, Any]]:
        """Evaluate and filter discovered opportunities against candidate profile."""
        opps = state.market_context.get("opportunities", [])
        # Use resume skills if available, otherwise fall back to candidate_context
        resume_skills = list(state.resume_context.get("skills", []))
        if not resume_skills:
            resume_skills = list(state.candidate_context.get("skills", []))
        candidate_titles = state.resume_context.get("titles", [])
        candidate_years = state.resume_context.get("experience_years", 0) or state.candidate_context.get("experience_years", 0)

        if not opps:
            return []

        from src.services.opportunity.opportunity_match_engine import get_opportunity_match_engine
        engine = get_opportunity_match_engine()
        candidate_blob = {
            "skills": resume_skills,
            "experience_years": candidate_years,
            "titles": candidate_titles,
            "target_role": state.candidate_context.get("target_role", ""),
        }

        scored = []
        for opp in opps:
            result = engine.score(opp, candidate_blob)
            if result["overall_score"] >= getattr(settings, "OPPORTUNITY_MIN_SCORE_FOR_ACTION", 0.4):
                opp["overall_score"] = result["overall_score"]
                opp["dimension_scores"] = result["dimension_scores"]
                opp["confidence"] = result["confidence"]
                opp["skill_overlap"] = result["dimension_scores"].get("skill_overlap", 0)
                scored.append(opp)

        scored.sort(key=lambda o: o.get("overall_score", 0), reverse=True)
        return scored

    def _compute_confidence(self, state: DiscoveryState) -> float:
        base = 0.5
        if state.resume_context.get("status") == "retrieved":
            base += 0.15
        if state.market_context.get("opportunities"):
            base += 0.15
        if state.discovered_opportunities:
            base += 0.2
        return min(base, 0.95)


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[OpportunityDiscoveryAgent] = None


def get_opportunity_discovery_agent() -> OpportunityDiscoveryAgent:
    global _agent
    if _agent is None:
        _agent = OpportunityDiscoveryAgent()
    return _agent


def reset_opportunity_discovery_agent() -> None:
    global _agent
    _agent = None
