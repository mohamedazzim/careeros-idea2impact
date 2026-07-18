"""Audit and safely clean duplicate Greenhouse job rows.

The script supports a dry-run mode that prints a reversible cleanup plan and an
apply mode that:

1. Selects a canonical survivor row for each confirmed duplicate group.
2. Reassigns non-unique child-table references to the survivor.
3. Preserves one row in unique child tables, preferring the survivor-linked row.
4. Deletes the duplicate Greenhouse job rows only after the references are
   handled.

Usage:
    cd backend && python -m scripts.cleanup_greenhouse_duplicates --dry-run
    cd backend && python -m scripts.cleanup_greenhouse_duplicates --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text

from src.db.session import async_session
from src.models.jobs import Job

SQL_DIR = ROOT / "queries" / "greenhouse_cleanup"


@dataclass(frozen=True)
class DuplicateJobRow:
    id: int
    job_uid: str
    source_job_id: str | None
    source_url: str | None
    apply_url: str | None
    company: str | None
    title: str
    location: str | None
    fetched_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ReferencePlan:
    table: str
    column: str
    unique: bool
    total_references: int
    rows_to_keep: list[int]
    rows_to_delete: list[int]
    rows_to_reassign: list[int]


@dataclass(frozen=True)
class DuplicatePlan:
    duplicate_group_key: str
    survivor_job_id: int
    duplicate_job_ids_to_merge_or_delete: list[int]
    reference_counts_per_duplicate: dict[int, dict[str, int]]
    planned_action: str


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _render_sql(name: str, **replacements: Any) -> str:
    sql = _load_sql(name)
    for key, value in replacements.items():
        sql = sql.replace(f"{{{{{key}}}}}", str(value))
    return sql


def _group_key(job: DuplicateJobRow) -> str:
    url = _normalize_url(job.source_url or job.apply_url or job.source_job_id)
    return " | ".join(
        [
            _normalize("greenhouse"),
            url,
            _normalize(job.company),
            _normalize(job.title),
            _normalize(job.location),
        ]
    )


def _survivor_sort_key(job: DuplicateJobRow) -> tuple[Any, ...]:
    return (
        job.fetched_at or datetime.min,
        job.updated_at or datetime.min,
        1 if job.apply_url else 0,
        1 if job.source_url else 0,
        -job.id,
    )


def _select_survivor(records: list[DuplicateJobRow]) -> DuplicateJobRow:
    if not records:
        raise ValueError("records must not be empty")
    return max(records, key=_survivor_sort_key)


async def _load_greenhouse_jobs() -> list[DuplicateJobRow]:
    async with async_session() as db:
        rows = (await db.execute(
            select(Job).where(Job.source == "greenhouse").order_by(
                Job.fetched_at.desc().nullslast(),
                Job.updated_at.desc().nullslast(),
                Job.id.asc(),
            )
        )).scalars().all()

    return [
        DuplicateJobRow(
            id=row.id,
            job_uid=row.job_uid,
            source_job_id=row.source_job_id,
            source_url=row.source_url,
            apply_url=row.apply_url,
            company=row.company,
            title=row.title,
            location=row.location,
            fetched_at=row.fetched_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def _load_fk_metadata() -> list[dict[str, Any]]:
    async with async_session() as db:
        result = await db.execute(text(_load_sql("load_fk_metadata.sql")))
        return [dict(row._mapping) for row in result]


async def _load_column_names(table_name: str) -> set[str]:
    async with async_session() as db:
        result = await db.execute(text(_render_sql("load_column_names.sql", table_name=table_name)))
        return {row[0] for row in result.all()}


def _build_duplicate_groups(jobs: list[DuplicateJobRow]) -> dict[str, list[DuplicateJobRow]]:
    groups: dict[str, list[DuplicateJobRow]] = defaultdict(list)
    for job in jobs:
        groups[_group_key(job)].append(job)
    return {key: value for key, value in groups.items() if len(value) > 1}


async def _count_references(
    duplicate_ids: list[int],
    fk_metadata: list[dict[str, Any]],
) -> dict[str, dict[int, int]]:
    counts_by_table: dict[str, dict[int, int]] = {}
    async with async_session() as db:
        for meta in fk_metadata:
            table_name = meta["table_name"]
            column_name = meta["column_name"]
            result = await db.execute(
                text(
                    _render_sql(
                        "count_references.sql",
                        table_name=table_name,
                        column_name=column_name,
                    )
                ),
                {"job_ids": duplicate_ids},
            )
            table_counts = {
                int(row._mapping["job_id"]): int(row._mapping["ref_count"])
                for row in result
            }
            if table_counts:
                counts_by_table[table_name] = table_counts
    return counts_by_table


def _reference_summary_for_job(job_id: int, counts_by_table: dict[str, dict[int, int]]) -> dict[str, int]:
    return {table: counts[job_id] for table, counts in counts_by_table.items() if job_id in counts}


async def _build_reference_plans(
    survivor_id: int,
    duplicate_ids: list[int],
    fk_metadata: list[dict[str, Any]],
) -> list[ReferencePlan]:
    plans: list[ReferencePlan] = []
    async with async_session() as db:
        for meta in fk_metadata:
            table_name = meta["table_name"]
            column_name = meta["column_name"]
            unique = bool(meta["column_is_unique"])

            if unique:
                columns = await _load_column_names(table_name)
                timestamp_candidates = [
                    column
                    for column in ("updated_at", "created_at", "ingested_at")
                    if column in columns
                ]
                if not timestamp_candidates:
                    timestamp_expr = "id"
                elif len(timestamp_candidates) == 1:
                    timestamp_expr = timestamp_candidates[0]
                else:
                    timestamp_expr = "COALESCE(" + ", ".join(timestamp_candidates) + ")"

                result = await db.execute(
                    text(
                        _render_sql(
                            "unique_rows.sql",
                            table_name=table_name,
                            column_name=column_name,
                            timestamp_expr=timestamp_expr,
                        )
                    ),
                    {"job_ids": [survivor_id, *duplicate_ids]},
                )
                rows = [dict(row._mapping) for row in result]
                if not rows:
                    continue

                survivor_rows = [row for row in rows if int(row["job_id"]) == survivor_id]
                if survivor_rows:
                    keep_row_id = max(
                        survivor_rows,
                        key=lambda row: (
                            row["sort_value"] or datetime.min,
                            -int(row["id"]),
                        ),
                    )["id"]
                else:
                    keep_row_id = max(
                        rows,
                        key=lambda row: (
                            row["sort_value"] or datetime.min,
                            -int(row["id"]),
                        ),
                    )["id"]

                rows_to_keep = [int(keep_row_id)]
                rows_to_delete = [int(row["id"]) for row in rows if int(row["id"]) != int(keep_row_id)]
                rows_to_reassign = []
                plans.append(
                    ReferencePlan(
                        table=table_name,
                        column=column_name,
                        unique=True,
                        total_references=len(rows),
                        rows_to_keep=rows_to_keep,
                        rows_to_delete=rows_to_delete,
                        rows_to_reassign=rows_to_reassign,
                    )
                )
            else:
                result = await db.execute(
                    text(
                        _render_sql(
                            "nonunique_count_references.sql",
                            table_name=table_name,
                            column_name=column_name,
                        )
                    ),
                    {"job_ids": duplicate_ids},
                )
                total = int(result.scalar_one() or 0)
                if not total:
                    continue
                plans.append(
                    ReferencePlan(
                        table=table_name,
                        column=column_name,
                        unique=False,
                        total_references=total,
                        rows_to_keep=[],
                        rows_to_delete=[],
                        rows_to_reassign=duplicate_ids,
                    )
                )
    return plans


async def _apply_reference_plans(
    survivor_id: int,
    duplicate_ids: list[int],
    plans: list[ReferencePlan],
) -> dict[str, int]:
    remapped_rows = 0
    deleted_rows = 0

    async with async_session() as db:
        async with db.begin():
            for plan in plans:
                if plan.unique:
                    if plan.rows_to_keep:
                        keeper_id = plan.rows_to_keep[0]
                        if keeper_id != survivor_id:
                            await db.execute(
                                text(_render_sql("unique_adopt_row.sql", table_name=plan.table)),
                                {"survivor_id": survivor_id, "keeper_id": keeper_id},
                            )

                    if plan.rows_to_delete:
                        result = await db.execute(
                            text(_render_sql("unique_delete_rows.sql", table_name=plan.table)),
                            {"row_ids": plan.rows_to_delete},
                        )
                        deleted_rows += int(result.rowcount or 0)
                else:
                    if not duplicate_ids:
                        continue
                    result = await db.execute(
                        text(
                            _render_sql(
                                "nonunique_update_rows.sql",
                                table_name=plan.table,
                                column_name=plan.column,
                            )
                        ),
                        {"survivor_id": survivor_id, "job_ids": duplicate_ids},
                    )
                    remapped_rows += int(result.rowcount or 0)

            result = await db.execute(text(_load_sql("delete_jobs.sql")), {"job_ids": duplicate_ids})
            deleted_rows += int(result.rowcount or 0)

    return {"remapped_rows": remapped_rows, "deleted_rows": deleted_rows}


async def build_cleanup_report() -> list[DuplicatePlan]:
    jobs = await _load_greenhouse_jobs()
    duplicate_groups = _build_duplicate_groups(jobs)
    fk_metadata = await _load_fk_metadata()

    plans: list[DuplicatePlan] = []
    for group_key, records in duplicate_groups.items():
        survivor = _select_survivor(records)
        duplicate_records = [record for record in records if record.id != survivor.id]
        duplicate_ids = [record.id for record in duplicate_records]
        counts_by_table = await _count_references(duplicate_ids, fk_metadata)
        reference_counts = {
            record.id: _reference_summary_for_job(record.id, counts_by_table)
            for record in duplicate_records
        }
        child_plans = await _build_reference_plans(survivor.id, duplicate_ids, fk_metadata)
        action = "delete_only" if not any(plan.total_references for plan in child_plans) else "remap_then_delete"
        plans.append(
            DuplicatePlan(
                duplicate_group_key=group_key,
                survivor_job_id=survivor.id,
                duplicate_job_ids_to_merge_or_delete=duplicate_ids,
                reference_counts_per_duplicate=reference_counts,
                planned_action=action,
            )
        )
    return plans


async def _apply_cleanup() -> dict[str, int]:
    jobs = await _load_greenhouse_jobs()
    duplicate_groups = _build_duplicate_groups(jobs)
    fk_metadata = await _load_fk_metadata()

    total_groups = 0
    total_duplicate_rows = 0
    total_remapped_rows = 0
    total_deleted_rows = 0

    for records in duplicate_groups.values():
        survivor = _select_survivor(records)
        duplicate_ids = [record.id for record in records if record.id != survivor.id]
        if not duplicate_ids:
            continue

        plans = await _build_reference_plans(survivor.id, duplicate_ids, fk_metadata)
        result = await _apply_reference_plans(survivor.id, duplicate_ids, plans)
        total_groups += 1
        total_duplicate_rows += len(duplicate_ids)
        total_remapped_rows += result["remapped_rows"]
        total_deleted_rows += result["deleted_rows"]

    return {
        "duplicate_groups_cleaned": total_groups,
        "duplicate_rows_removed": total_duplicate_rows,
        "child_rows_remapped": total_remapped_rows,
        "child_rows_deleted": total_deleted_rows,
    }


async def _post_cleanup_counts() -> dict[str, Any]:
    async with async_session() as db:
        total = await db.execute(
            text(_load_sql("count_greenhouse_jobs.sql"))
        )
        duplicate_groups = await db.execute(
            text(_load_sql("count_greenhouse_duplicate_groups.sql"))
        )
        return {
            "greenhouse_rows": int(total.scalar_one() or 0),
            "duplicate_groups_remaining": int(duplicate_groups.scalar_one() or 0),
        }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Audit or clean duplicate Greenhouse jobs")
    parser.add_argument("--apply", action="store_true", help="Apply the cleanup in a transaction")
    parser.add_argument("--dry-run", action="store_true", help="Print the cleanup plan without mutating the DB")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        args.dry_run = True

    report = await build_cleanup_report()
    summary = {
        "duplicate_groups_found": len(report),
        "duplicate_rows_to_remove": sum(len(item.duplicate_job_ids_to_merge_or_delete) for item in report),
        "groups_needing_reference_handling": sum(1 for item in report if item.planned_action != "delete_only"),
    }
    print(json.dumps(summary, sort_keys=True))
    for item in report:
        print(json.dumps(asdict(item), default=str, sort_keys=True))

    if args.dry_run:
        return

    cleanup_result = await _apply_cleanup()
    print(json.dumps({"cleanup_result": cleanup_result}, sort_keys=True))
    post = await _post_cleanup_counts()
    print(json.dumps({"post_cleanup_counts": post}, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
