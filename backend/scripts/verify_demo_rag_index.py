from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Iterable, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.db.qdrant import get_qdrant
from src.services.rag.service import (
    DemoRagChatRequest,
    DemoRagService,
)
from src.services.vector_store.qdrant_service import get_qdrant_service


REPO_ROOT = Path(__file__).resolve().parents[2]


def _format_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _default_questions() -> List[str]:
    return [
        "What is CareerOS?",
        "Which agents are implemented?",
        "How does the RAG pipeline work?",
        "What does careeros_rag_docs mean?",
    ]


def _print_heading(title: str) -> None:
    print()
    print("=" * 88)
    print(title)
    print("=" * 88)


async def _sample_payloads(service: DemoRagService, sample_count: int) -> None:
    qdrant = await get_qdrant()
    points, _ = await qdrant.scroll(
        collection_name=service.collection_name,
        limit=sample_count,
        with_payload=True,
        with_vectors=False,
    )

    print(f"Sample payloads from {service.collection_name} ({len(points)} shown):")
    for index, point in enumerate(points, start=1):
        payload = point.payload or {}
        print(
            json.dumps(
                {
                    "sample": index,
                    "point_id": str(point.id),
                    "chunk_id": payload.get("chunk_id"),
                    "doc_name": payload.get("doc_name"),
                    "section_title": payload.get("section_title"),
                    "source_path": payload.get("source_path"),
                    "chunk_index": payload.get("chunk_index"),
                    "updated_at": payload.get("updated_at"),
                    "content_hash": payload.get("content_hash"),
                    "text_preview": str(payload.get("text") or "")[:180],
                },
                indent=2,
                ensure_ascii=False,
            )
        )


async def _sample_retrievals(service: DemoRagService, questions: Iterable[str], top_k: int) -> None:
    for question in questions:
        result = await service.retrieve(question, top_k=top_k)
        print(f"\nQ: {question}")
        print(f"  status={result.status} top_score={result.top_score:.4f} reason={result.reason}")
        for hit in result.chunks[:3]:
            print(
                "  - "
                f"{hit.doc_name} :: {hit.section_title} "
                f"({hit.source_path}) score={hit.score:.4f}"
            )


async def _sample_chat_answer(service: DemoRagService, question: str, top_k: int) -> None:
    retrieval = await service.retrieve(question, top_k=top_k)
    answer = await service._generate_answer(  # noqa: SLF001
        question=question,
        retrieval=retrieval,
        session_id="verify-demo-rag",
        viewer_role="mentor",
    )

    print("\nSample chatbot answer:")
    print(f"  question={question}")
    print(f"  status={answer.status}")
    print(f"  confidence={answer.confidence:.4f}")
    print(f"  needs_verification={answer.needs_verification}")
    print(f"  citations={len(answer.citations)}")
    print(f"  answer={answer.answer}")
    if answer.citations:
        print("  citation_details=")
        for citation in answer.citations[:3]:
            print(
                "    - "
                f"{citation.doc_name} :: {citation.section_title} "
                f"({citation.source_path}) score={citation.score:.4f}"
            )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify docs/rag indexing and Qdrant storage.")
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Recreate the Qdrant collection and reindex docs/rag before verification.",
    )
    parser.add_argument(
        "--sample-payloads",
        type=int,
        default=3,
        help="How many Qdrant payloads to print as samples.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=6,
        help="Top-k retrieval limit used for sample questions.",
    )
    parser.add_argument(
        "--sample-questions",
        type=int,
        default=4,
        help="How many golden questions to sample for retrieval verification.",
    )
    args = parser.parse_args()

    service = DemoRagService()
    files = service._discover_markdown_files()  # noqa: SLF001 - verification helper
    file_counts = {}
    empty_docs = []
    total_chunks = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = service._parse_markdown(path, text)  # noqa: SLF001 - verification helper
        file_counts[_format_rel(path)] = len(chunks)
        total_chunks += len(chunks)
        if not chunks:
            empty_docs.append(_format_rel(path))

    _print_heading("RAG DOC INVENTORY")
    print(f"docs_path={_format_rel(service.docs_path)}")
    print(f"markdown_files_found={len(files)}")
    print(f"chunks_pre_index={total_chunks}")
    print(f"empty_docs={empty_docs if empty_docs else '[]'}")
    for rel_path, count in file_counts.items():
        print(f"  - {rel_path}: {count} chunks")

    _print_heading("INDEXING")
    index_response = await service.index_docs(recreate=args.reindex)
    print(index_response.model_dump_json(indent=2))

    qdrant_service = get_qdrant_service()
    collection_info = await qdrant_service.get_collection_info(service.collection_name)

    _print_heading("QDRANT COLLECTION")
    print(json.dumps(collection_info, indent=2, ensure_ascii=False))

    points_count = int(collection_info.get("points_count") or 0)
    qdrant_match = points_count == index_response.successful_upserts == index_response.chunks_indexed
    print(f"point_count_matches_index={qdrant_match}")

    _print_heading("HEALTH")
    health = await service.health()
    print(health.model_dump_json(indent=2))

    _print_heading("SAMPLE PAYLOADS")
    await _sample_payloads(service, sample_count=max(1, args.sample_payloads))

    golden_questions = await service.golden_questions()
    sampled_questions = [item.question for item in golden_questions[: max(1, args.sample_questions)]]
    if not sampled_questions:
        sampled_questions = _default_questions()

    _print_heading("SAMPLE RETRIEVALS")
    await _sample_retrievals(service, sampled_questions, top_k=max(1, args.top_k))

    _print_heading("SAMPLE CHAT ANSWER")
    await _sample_chat_answer(service, sampled_questions[0], top_k=max(1, args.top_k))

    issues = []
    if len(files) != index_response.files_indexed:
        issues.append("file_count_mismatch")
    if total_chunks != index_response.chunks_indexed:
        issues.append("chunk_count_mismatch")
    if index_response.failed_chunks:
        issues.append("failed_chunks_present")
    if points_count != index_response.successful_upserts:
        issues.append("qdrant_point_count_mismatch")
    if empty_docs:
        issues.append("empty_docs_present")
    if not health.qdrant_ready:
        issues.append("qdrant_not_ready")
    if not health.qdrant_collection_ready:
        issues.append("qdrant_collection_missing")

    _print_heading("SUMMARY")
    print(f"issues={issues if issues else '[]'}")
    print(f"files_found={len(files)}")
    print(f"chunks_generated={total_chunks}")
    print(f"qdrant_points={points_count}")
    print(f"successful_upserts={index_response.successful_upserts}")
    print(f"failed_chunks={index_response.failed_chunks}")

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
