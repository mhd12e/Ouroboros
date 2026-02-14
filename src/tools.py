"""Direct backend tools for the agent — bypasses sandbox for security/performance."""
import json
from src.db_admin_tool import db_query
from src.rag import retrieve_similar, retrieve_documents
from src.file_tools import read_file, write_file, edit_file, list_files, run_command

def execute_tool(tool_name: str, args_json: str) -> str:
    """Execute a trusted backend tool.
    
    Args:
        tool_name: Tool name (sql_db, rag_search, read_file, etc.)
        args_json: JSON string or dict of arguments
        
    Returns:
        String result (success data or error message)
    """
    try:
        # Parse args (handles both JSON string and pre-parsed dict)
        if isinstance(args_json, dict):
            args = args_json
        else:
            try:
                args = json.loads(args_json)
            except:
                return f"ERROR: Invalid JSON arguments: {args_json}"
        
        # === DB TOOLS ===
        if tool_name == "sql_db":
            query = args.get("query")
            if not query: return "ERROR: Missing 'query'"
            rows = db_query(query)
            if isinstance(rows, list) and len(rows) > 0 and "error" in rows[0]:
                return f"SQL ERROR: {rows[0]['error']}"
            if not rows: return "No results found."
            result_str = json.dumps(rows, indent=2, default=str)
            return (result_str[:5000] + "\n... (truncated)") if len(result_str) > 5000 else result_str

        elif tool_name == "rag_search":
            query = args.get("query")
            if not query: return "ERROR: Missing 'query'"
            results = retrieve_similar(query, top_k=3)
            if not results: return "No similar solutions found."
            formatted = []
            for r in results:
                formatted.append(f"Task: {r['task']}\nCode Snippet: {r['code'][:200]}...\nResult: {r['result'][:200]}...")
            return "\n\n".join(formatted)

        elif tool_name == "search_documents":
            query = args.get("query")
            if not query: return "ERROR: Missing 'query'"
            results = retrieve_documents(query)
            if not results: return "No relevant documents found."
            return "\n\n".join([f"--- Source: {d['filename']} ---\n{d['content']}" for d in results])

        # === FILE TOOLS ===
        elif tool_name == "read_file":
            path = args.get("path")
            if not path: return "ERROR: Missing 'path'"
            return read_file(path, args.get("start_line"), args.get("end_line"))

        elif tool_name == "write_file":
            path = args.get("path")
            content = args.get("content")
            if not path or content is None: return "ERROR: Missing 'path' or 'content'"
            return write_file(path, content)

        elif tool_name == "edit_file":
            path = args.get("path")
            old_text = args.get("old_text")
            new_text = args.get("new_text")
            if not path or old_text is None or new_text is None: return "ERROR: Missing 'path', 'old_text', or 'new_text'"
            return edit_file(path, old_text, new_text)

        elif tool_name == "list_files":
            path = args.get("path", ".")
            return list_files(path, args.get("max_depth", 2))

        elif tool_name == "run_command":
            cmd = args.get("command")
            if not cmd: return "ERROR: Missing 'command'"
            return run_command(cmd, args.get("cwd"))

        else:
            return f"ERROR: Unknown tool '{tool_name}'"

    except Exception as e:
        return f"TOOL EXECUTION ERROR: {str(e)}"
