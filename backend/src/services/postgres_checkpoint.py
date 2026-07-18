"""LangGraph 0.0.69 compatible PostgreSQL checkpoint saver."""
from __future__ import annotations
from typing import AsyncIterator
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from sqlalchemy import text
from src.db.session import async_session

class PostgresCheckpointSaver(BaseCheckpointSaver):
    def get_tuple(self, config): raise RuntimeError("Use async graph execution with PostgreSQL checkpoints")
    def list(self, config, **kwargs): raise RuntimeError("Use async graph execution with PostgreSQL checkpoints")
    def put(self, config, checkpoint, metadata): raise RuntimeError("Use async graph execution with PostgreSQL checkpoints")
    async def aget_tuple(self, config):
        tid=config["configurable"]["thread_id"]; ts=config["configurable"].get("thread_ts")
        query="SELECT thread_ts,checkpoint,metadata FROM langgraph_checkpoints WHERE thread_id=:tid"
        if ts: query += " AND thread_ts=:ts"
        query += " ORDER BY thread_ts DESC LIMIT 1"
        async with async_session() as db:
            row=(await db.execute(text(query),{"tid":tid,"ts":ts})).first()
        if not row: return None
        return CheckpointTuple(config={"configurable":{"thread_id":tid,"thread_ts":row.thread_ts}},checkpoint=self.serde.loads(row.checkpoint),metadata=self.serde.loads(row.metadata))
    async def alist(self, config, *, filter=None, before=None, limit=None) -> AsyncIterator[CheckpointTuple]:
        tid=config["configurable"]["thread_id"] if config else None
        query="SELECT thread_id,thread_ts,checkpoint,metadata FROM langgraph_checkpoints"
        params={}; clauses=[]
        if tid: clauses.append("thread_id=:tid"); params["tid"]=tid
        if before: clauses.append("thread_ts < :before"); params["before"]=before["configurable"]["thread_ts"]
        if clauses: query+=" WHERE "+" AND ".join(clauses)
        query+=" ORDER BY thread_ts DESC"
        if limit: query+=" LIMIT :limit"; params["limit"]=limit
        async with async_session() as db: rows=(await db.execute(text(query),params)).all()
        for row in rows:
            metadata=self.serde.loads(row.metadata)
            if not filter or all(metadata.get(k)==v for k,v in filter.items()):
                yield CheckpointTuple(config={"configurable":{"thread_id":row.thread_id,"thread_ts":row.thread_ts}},checkpoint=self.serde.loads(row.checkpoint),metadata=metadata)
    async def aput(self, config, checkpoint, metadata):
        tid=config["configurable"]["thread_id"]; ts=checkpoint["id"]
        async with async_session() as db:
            await db.execute(text("""INSERT INTO langgraph_checkpoints(thread_id,thread_ts,checkpoint,metadata)
            VALUES(:tid,:ts,:checkpoint,:metadata) ON CONFLICT(thread_id,thread_ts) DO UPDATE SET checkpoint=EXCLUDED.checkpoint,metadata=EXCLUDED.metadata"""),
            {"tid":tid,"ts":ts,"checkpoint":self.serde.dumps(checkpoint),"metadata":self.serde.dumps(metadata)})
            await db.commit()
        return {"configurable":{"thread_id":tid,"thread_ts":ts}}
