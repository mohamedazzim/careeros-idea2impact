"""Clean up duplicate VOICE_CALL CommunicationRequest rows.

For each (user_id, job_id) pair with multiple VOICE_CALL/phone_call records,
keeps the newest record and marks older duplicates as 'duplicate_suppressed'.
Does not delete rows — only updates communication_status.
"""
import asyncio
import sys
from collections import defaultdict

sys.path.insert(0, "/app")


async def main():
    from src.db.session import async_session
    from src.models.jobs import CommunicationRequest
    from sqlalchemy import select, func, update

    call_channels = ("VOICE_CALL", "phone_call")

    async with async_session() as db:
        rows = (await db.execute(
            select(CommunicationRequest)
            .where(CommunicationRequest.channel.in_(call_channels))
            .order_by(CommunicationRequest.created_at.desc())
        )).scalars().all()

        groups = defaultdict(list)
        for row in rows:
            key = (row.user_id, row.job_id)
            groups[key].append(row)

        cleaned = 0
        for key, records in groups.items():
            if len(records) <= 1:
                continue
            records.sort(key=lambda r: r.created_at, reverse=True)
            keep = records[0]
            for dup in records[1:]:
                if dup.communication_status not in ("duplicate_suppressed", "cancelled", "dry_run"):
                    dup.communication_status = "duplicate_suppressed"
                    dup.communication_result = {
                        "duplicate_suppressed": True,
                        "kept_id": keep.id,
                        "reason": f"older duplicate of id={keep.id}",
                    }
                    dup.updated_at = keep.created_at
                    cleaned += 1

        if cleaned:
            await db.commit()

        print(f"duplicate_groups_found={sum(1 for v in groups.values() if len(v) > 1)}")
        print(f"records_marked_duplicate_suppressed={cleaned}")

        remaining = (await db.execute(
            select(func.count()).select_from(CommunicationRequest).where(
                CommunicationRequest.channel.in_(call_channels),
                CommunicationRequest.communication_status.notin_(
                    ["duplicate_suppressed", "cancelled", "dry_run", "failed"]
                ),
            )
        )).scalar()
        print(f"active_call_records_remaining={remaining}")


asyncio.run(main())
