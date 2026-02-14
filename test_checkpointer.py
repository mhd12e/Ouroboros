from src.checkpointer import ClickHouseCheckpointer
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
import uuid
import time
import json

cp_saver = ClickHouseCheckpointer()

thread_id = f"test-{uuid.uuid4()}"
config = {"configurable": {"thread_id": thread_id}}

cp_id = str(uuid.uuid4())
ts = time.time()
cp = {
    "v": 1,
    "id": cp_id,
    "ts": ts,
    "channel_values": {"output": "hello"},
    "channel_versions": {"output": 1},
    "versions_seen": {"__start__": {}},
    "pending_sends": [],
}
metadata = {"source": "test", "step": 1, "writes": {"output": "hello"}}

print(f"Storing checkpoint {cp_id}...")
cp_saver.put(config, cp, metadata, {})

print("Retrieving checkpoint...")
tuple_res = cp_saver.get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id}})

if tuple_res:
    print(f"Version: {tuple_res.checkpoint['v']}")
    print(f"Output: {tuple_res.checkpoint['channel_values']['output']}")
    print(f"Metadata: {tuple_res.metadata}")
    print("SUCCESS")
else:
    print("FAILURE: Checkpoint not found")
