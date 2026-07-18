import asyncio
from qdrant_client.models import PointStruct

from src.db.repositories.domain_repositories import JobRepository
from src.db.session import async_session
from src.services.embedding.nvembed_service import NVEmbedV1Service
from src.services.vector_store.qdrant_service import QdrantService


async def main() -> None:
    qdrant = QdrantService()
    await qdrant.recreate_collection("careeros_jobs")
    async with async_session() as db:
        repo = JobRepository(db)
        jobs = await repo.find_active(limit=1000)
        embedder = NVEmbedV1Service()
        points = []
        for job in jobs:
            text = f"{job.title} at {job.company}. {job.description or ''}".strip()[:2000]
            if not text:
                continue
            vec = await embedder.embed_query(text)
            if not vec:
                continue
            points.append(
                PointStruct(
                    id=hash(f"job_{job.id}") & 0x7FFFFFFFFFFFFFFF,
                    vector=vec,
                    payload={
                        "job_id": str(job.id),
                        "job_uid": job.job_uid,
                        "title": job.title,
                        "company": job.company or "",
                        "source": job.source or "",
                        "source_job_id": job.source_job_id or job.job_uid,
                        "source_url": job.source_url or "",
                        "ingested_at": job.ingested_at.isoformat() if job.ingested_at else "",
                        "skills": job.skills_required or [],
                    },
                )
            )
        if points:
            await qdrant.upsert_points("careeros_jobs", points, validate=False)
        print({"jobs": len(jobs), "points": len(points)})


if __name__ == "__main__":
    asyncio.run(main())
