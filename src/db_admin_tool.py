"""Database admin tool — lets the agent autonomously manage ClickHouse tables."""
import time
from src.db import get_client


def db_execute(sql: str) -> str:
    """Execute a DDL/DML SQL command. Returns result or error string."""
    try:
        client = get_client()
        if client is None:
            return "OFFLINE — ClickHouse not reachable"
        result = client.command(sql)
        return str(result) if result else "OK"
    except Exception as e:
        return f"ERROR: {e}"


def db_query(sql: str) -> list:
    """Execute a SELECT query, return rows as list of dicts."""
    try:
        client = get_client()
        if client is None:
            return [{"error": "OFFLINE — ClickHouse not reachable"}]
        
        result = client.query(sql)
        columns = result.column_names
        rows = []
        for row in result.result_rows:
            rows.append(dict(zip(columns, row)))
        return rows
    except Exception as e:
        return [{"error": str(e)}]


def db_insert(table: str, data: list, column_names: list) -> str:
    """Batch insert rows into a table.
    
    Args:
        table: Table name
        data: List of tuples (rows)
        column_names: List of column names
    """
    try:
        client = get_client()
        if client is None:
            return "OFFLINE — ClickHouse not reachable"
            
        client.insert(table, data, column_names=column_names)
        return f"OK — inserted {len(data)} rows"
    except Exception as e:
        return f"ERROR: {e}"


def log_execution(task: str, success: bool, duration_ms: float,
                  error_type: str = "", error_message: str = "",
                  iteration_count: int = 0, thread_id: str = ""):
    """Log an agent execution to the metrics table."""
    try:
        client = get_client()
        if client is None:
            return
            
        client.insert(
            'agent_metrics',
            [[thread_id, task[:500], success, duration_ms, 
              error_type, error_message[:1000], iteration_count, 'claude-3-sonnet']],
            column_names=['thread_id', 'task', 'success', 'duration_ms',
                         'error_type', 'error_message', 'iteration_count', 'model']
        )
    except Exception as e:
        print(f"[Metrics] Failed to log: {e}")


def get_recovery_rate(limit: int = 100) -> dict:
    """Get success/failure stats for the recovery rate chart."""
    try:
        rows = db_query(f"""
            SELECT 
                success,
                count() as cnt,
                avg(duration_ms) as avg_duration,
                avg(iteration_count) as avg_iterations
            FROM agent_metrics
            ORDER BY created_at DESC
            LIMIT {limit}
        """)
        
        # Check for offline error in rows
        if rows and isinstance(rows[0], dict) and "error" in rows[0]:
            return {"total": 0, "successes": 0, "rate": 0, "rows": [], "error": rows[0]["error"]}
            
        total = sum(r.get('cnt', 0) for r in rows if 'error' not in r)
        successes = sum(r.get('cnt', 0) for r in rows if r.get('success') and 'error' not in r)
        return {
            "total": total,
            "successes": successes,
            "rate": (successes / total * 100) if total > 0 else 0,
            "rows": rows
        }
    except Exception as e:
        return {"total": 0, "successes": 0, "rate": 0, "rows": [], "error": str(e)}
