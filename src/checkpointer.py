"""Custom LangGraph checkpointer backed by ClickHouse."""
import json
from typing import Any, Iterator, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.load import dumps, loads
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from src.db import get_client


class ClickHouseCheckpointer(BaseCheckpointSaver):
    """Persists LangGraph agent state to ClickHouse using langchain_core serialization."""
    
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[dict] = None,
    ) -> RunnableConfig:
        """Store a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_id = config["configurable"].get("checkpoint_id", "")
        
        # Serialize using LangChain dumps (returns JSON string)
        checkpoint_data = dumps(checkpoint)
        metadata_data = json.dumps(metadata) if metadata else "{}"
        
        client = get_client()
        client.insert(
            "checkpoints",
            [[thread_id, checkpoint_ns, checkpoint_id, parent_id,
              checkpoint_data, metadata_data]],
            column_names=["thread_id", "checkpoint_ns", "checkpoint_id",
                         "parent_checkpoint_id", "checkpoint_data", "metadata_data"]
        )
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
    
    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Store intermediate writes for fault tolerance."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id", "")
        
        rows = []
        for idx, (channel, value) in enumerate(writes):
            blob = dumps(value)
            type_str = type(value).__name__
            rows.append([thread_id, checkpoint_ns, checkpoint_id, task_id,
                        idx, channel, type_str, blob])
        
        if rows:
            client = get_client()
            client.insert(
                "checkpoint_writes",
                rows,
                column_names=["thread_id", "checkpoint_ns", "checkpoint_id",
                             "task_id", "idx", "channel", "type", "blob"]
            )
    
    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Retrieve the latest (or specific) checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id", None)
        
        client = get_client()
        
        if checkpoint_id:
            query = f"""
                SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata_data
                FROM checkpoints FINAL
                WHERE thread_id = '{thread_id}' 
                  AND checkpoint_ns = '{checkpoint_ns}'
                  AND checkpoint_id = '{checkpoint_id}'
                LIMIT 1
            """
        else:
            query = f"""
                SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata_data
                FROM checkpoints FINAL
                WHERE thread_id = '{thread_id}' 
                  AND checkpoint_ns = '{checkpoint_ns}'
                ORDER BY created_at DESC
                LIMIT 1
            """
        
        result = client.query(query)
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        cp_id, parent_id, cp_data, meta_data = row
        
        checkpoint = loads(cp_data)
        metadata = json.loads(meta_data) if meta_data else {}
        
        cfg = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": cp_id,
            }
        }
        parent_cfg = None
        if parent_id:
            parent_cfg = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_id,
                }
            }
        
        # Get pending writes
        writes_result = client.query(f"""
            SELECT task_id, channel, type, blob
            FROM checkpoint_writes
            WHERE thread_id = '{thread_id}'
              AND checkpoint_ns = '{checkpoint_ns}'
              AND checkpoint_id = '{cp_id}'
            ORDER BY idx ASC
        """)
        
        pending_writes = []
        for w_row in writes_result.result_rows:
            task_id, channel, type_str, blob = w_row
            value = loads(blob)
            pending_writes.append((task_id, channel, value))
        
        return CheckpointTuple(
            config=cfg,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_cfg,
            pending_writes=pending_writes,
        )
    
    def list(
        self,
        config: Optional[RunnableConfig] = None,
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints for a thread."""
        if not config:
            return
        
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        
        conditions = [
            f"thread_id = '{thread_id}'",
            f"checkpoint_ns = '{checkpoint_ns}'",
        ]
        
        if before:
            before_id = before["configurable"].get("checkpoint_id", "")
            if before_id:
                conditions.append(f"checkpoint_id < '{before_id}'")
        
        where = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit else "LIMIT 100"
        
        client = get_client()
        result = client.query(f"""
            SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata_data
            FROM checkpoints FINAL
            WHERE {where}
            ORDER BY created_at DESC
            {limit_clause}
        """)
        
        for row in result.result_rows:
            cp_id, parent_id, cp_data, meta_data = row
            checkpoint = loads(cp_data)
            metadata = json.loads(meta_data) if meta_data else {}
            
            cfg = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": cp_id,
                }
            }
            parent_cfg = None
            if parent_id:
                parent_cfg = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_id,
                    }
                }
            
            yield CheckpointTuple(
                config=cfg,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_cfg,
            )
