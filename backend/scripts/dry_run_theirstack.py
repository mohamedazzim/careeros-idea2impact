"""Safe dry-run helper for TheirStack payload inspection and preview fetches."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_repo_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_repo_env()

from src.integrations.theirstack.client import TheirStackClient
from src.integrations.theirstack.sync_service import (
    NON_TECH_TITLE_EXCLUDES,
    TheirStackSyncService,
    build_theirstack_indian_tech_jobs_payload,
)


def _default_resume_profile() -> Dict[str, Any]:
    return {
        "skills": ["Python", "SQL", "FastAPI"],
        "education": ["MCA"],
        "location": "India",
        "target_role": "Software Engineer",
    }


async def _run(limit: int, page: int, since_days: int, fetch: bool) -> int:
    service = TheirStackSyncService()
    client = service.client if isinstance(service.client, TheirStackClient) else TheirStackClient()

    payload = build_theirstack_indian_tech_jobs_payload(
        limit=limit,
        page=page,
        since_days=since_days,
        preview=False,
        title_terms=service._build_title_terms(_default_resume_profile(), {}),
        negative_title_terms=service._dedupe_terms(NON_TECH_TITLE_EXCLUDES, limit=20),
        skill_terms=service._build_skill_terms(_default_resume_profile(), {}),
    )
    preview_payload = {**payload, "blur_company_data": True, "include_total_results": True, "limit": 1}

    print("TheirStack payload summary")
    print(json.dumps({
        "limit": payload.get("limit"),
        "page": payload.get("page"),
        "posted_at_gte": payload.get("posted_at_gte"),
        "countries": payload.get("job_country_code_or"),
        "company_type": payload.get("company_type"),
        "employment_statuses": payload.get("employment_statuses_or"),
        "property_exists_and": payload.get("property_exists_and"),
        "job_title_or_count": len(payload.get("job_title_or", [])),
        "job_title_not_count": len(payload.get("job_title_not", [])),
    }, indent=2))

    preview = await client.search_jobs(preview_payload, use_cache=False)
    if not preview.success:
        print(f"Preview failed: {preview.error}")
        return 1

    metadata = preview.data.get("metadata", {}) if isinstance(preview.data, dict) else {}
    print("Preview results")
    print(json.dumps({
        "total_results": metadata.get("total_results"),
        "total_companies": metadata.get("total_companies"),
        "fetched_count": preview.fetched_count,
        "selected_key_slot": preview.selected_key_slot,
    }, indent=2))

    if not fetch:
        print("Dry run complete. No DB write performed.")
        return 0

    result = await client.search_jobs(payload, use_cache=False)
    if not result.success:
        print(f"Fetch failed: {result.error}")
        return 1

    jobs = service._extract_jobs(result.data)
    sample_titles = [str(job.get("job_title") or job.get("title") or "unknown") for job in jobs[:5]]
    print("Sample sanitized job titles")
    print(json.dumps(sample_titles, indent=2))
    print("Dry run complete. No DB write performed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--fetch", action="store_true", help="Perform one real sanitized fetch after preview.")
    args = parser.parse_args()
    return asyncio.run(_run(args.limit, args.page, args.since_days, args.fetch))


if __name__ == "__main__":
    raise SystemExit(main())
