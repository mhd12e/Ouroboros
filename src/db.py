"""ClickHouse database connection and bootstrap."""
import os
import threading
import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

# Thread-local storage for client instances
_local = threading.local()
_bootstrapped = False

def get_client():
    """Get a thread-local ClickHouse client. Returns None if unreachable."""
    if not hasattr(_local, 'client'):
        try:
            _local.client = clickhouse_connect.get_client(
                host=os.getenv('CLICKHOUSE_HOST'),
                port=int(os.getenv('CLICKHOUSE_PORT', '8443')),
                username=os.getenv('CLICKHOUSE_USER', 'default'),
                password=os.getenv('CLICKHOUSE_PASSWORD', ''),
                secure=True,
                connect_timeout=5,
                send_receive_timeout=10,
            )
            # Quick connectivity test
            _local.client.command("SELECT 1")
            print(f"[DB] Connected to ClickHouse: {os.getenv('CLICKHOUSE_HOST')} (Thread: {threading.current_thread().name})")
        except Exception as e:
            print(f"[DB] ClickHouse unreachable (will work offline): {e}")
            _local.client = None
            
    return _local.client


def bootstrap():
    """Create required tables if they don't exist. No-op if DB unreachable."""
    global _bootstrapped
    if _bootstrapped:
        return
    
    client = get_client()
    if client is None:
        print("[DB] Bootstrap skipped — no connection")
        return
    
    try:
        # Agent metrics table
        client.command("""
            CREATE TABLE IF NOT EXISTS agent_metrics (
                id UUID DEFAULT generateUUIDv4(),
                thread_id String DEFAULT '',
                task String,
                success Bool,
                duration_ms Float64,
                error_type String DEFAULT '',
                error_message String DEFAULT '',
                iteration_count UInt32 DEFAULT 0,
                model String DEFAULT 'claude-3-sonnet',
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (created_at, id)
        """)
        
        # Solutions table for RAG (with vector index)
        client.command("SET allow_experimental_vector_similarity_index = 1")
        client.command("""
            CREATE TABLE IF NOT EXISTS solutions (
                id UUID DEFAULT generateUUIDv4(),
                task String,
                code String,
                result String,
                embedding Array(Float32),
                created_at DateTime DEFAULT now(),
                INDEX vec_idx embedding TYPE vector_similarity('hnsw', 'L2Distance', 1536)
            ) ENGINE = MergeTree()
            ORDER BY id
        """)
        
        # Checkpoints table
        client.command("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id String,
                checkpoint_ns String DEFAULT '',
                checkpoint_id String,
                parent_checkpoint_id String DEFAULT '',
                checkpoint_data String,
                metadata_data String,
                created_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(created_at)
            ORDER BY (thread_id, checkpoint_ns, checkpoint_id)
        """)
        
        # Checkpoint writes table
        client.command("""
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id String,
                checkpoint_ns String DEFAULT '',
                checkpoint_id String,
                task_id String,
                idx UInt32,
                channel String,
                type String DEFAULT '',
                blob String DEFAULT '',
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        """)
        
        # Memories table
        client.command("""
            CREATE TABLE IF NOT EXISTS memories (
                id UUID DEFAULT generateUUIDv4(),
                fact String,
                embedding Array(Float32),
                created_at DateTime DEFAULT now(),
                INDEX vec_idx embedding TYPE vector_similarity('hnsw', 'L2Distance', 1536)
            ) ENGINE = MergeTree()
            ORDER BY created_at
        """)
        
        # Documents table (RAG uploads)
        client.command("""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID DEFAULT generateUUIDv4(),
                filename String,
                chunk_index UInt32,
                content String,
                embedding Array(Float32),
                created_at DateTime DEFAULT now(),
                INDEX vec_idx embedding TYPE vector_similarity('hnsw', 'L2Distance', 1536)
            ) ENGINE = MergeTree()
            ORDER BY (filename, chunk_index)
        """)
        
        # Lessons table (Self-improvement)
        client.command("""
            CREATE TABLE IF NOT EXISTS lessons (
                id UUID DEFAULT generateUUIDv4(),
                prompt String,
                response String,
                lesson String,
                embedding Array(Float32),
                created_at DateTime DEFAULT now(),
                INDEX vec_idx embedding TYPE vector_similarity('hnsw', 'L2Distance', 1536)
            ) ENGINE = MergeTree()
            ORDER BY created_at
        """)
        
        _bootstrapped = True
        print("[DB] Bootstrap complete — all tables ready")
    except Exception as e:
        print(f"[DB] Bootstrap error: {e}")
