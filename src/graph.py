import time
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.cognition import Thinker, CodeGenerator, Synthesizer, Reflector, MemoryExtractor, QueryGenerator, SelfReflector
from src.sandbox import DockerSandbox
from src.rag import (
    retrieve_similar, format_rag_context, store_solution, 
    retrieve_memories, retrieve_recent_memories, store_memory,
    retrieve_lessons, store_lesson
)
from src.db_admin_tool import log_execution
from src.db import bootstrap as db_bootstrap, get_client as get_db_client
from src.checkpointer import ClickHouseCheckpointer
from src.tools import execute_tool

# Bootstrap DB tables (no-op if offline)
db_bootstrap()

# Initialize modules
thinker = Thinker()
code_generator = CodeGenerator()
synthesizer = Synthesizer()
reflector = Reflector()
try:
    memory_extractor = MemoryExtractor()
    query_generator = QueryGenerator()
    self_reflector = SelfReflector()
    print("[Graph] DSPy modules loaded")
except:
    memory_extractor = None
    query_generator = None
    self_reflector = None
    print("[Graph] DSPy modules failed to load")
    
sandbox = DockerSandbox()


def think_node(state: AgentState):
    """AI thinks about the user's message and decides if code is needed."""
    task = state['task']
    history = state.get('history', [])
    
    print(f"[think] Processing: {task[:80]}...")
    
    # RAG Context Logic:
    current_context = state.get('rag_context', '')
    if not current_context:
        try:
            # Generate optimized queries using DSPy
            queries = [task]
            if query_generator:
                generated = query_generator(task, history)
                if generated:
                    queries = generated
                    print(f"[think] Generated queries: {queries}")
            
            # Retrieval Loop (Multi-query)
            similar_raw = []
            memories_raw = []
            lessons_raw = []
            
            # Always check recent memories first
            memories_raw.extend(retrieve_recent_memories(5))
            
            for q in queries:
                similar_raw.extend(retrieve_similar(q, top_k=2))
                memories_raw.extend(retrieve_memories(q, limit=2))
                lessons_raw.extend(retrieve_lessons(q, limit=2))
            
            # Deduplicate
            seen_tasks = set()
            unique_similar = []
            for item in similar_raw:
                if item['task'] not in seen_tasks:
                    unique_similar.append(item)
                    seen_tasks.add(item['task'])
            
            seen_facts = set()
            unique_memories = []
            for mem in memories_raw:
                if mem not in seen_facts:
                    unique_memories.append(mem)
                    seen_facts.add(mem)

            seen_lessons = set()
            unique_lessons = []
            for l in lessons_raw:
                # Dedupe by lesson text
                if l['lesson'] not in seen_lessons:
                    unique_lessons.append(l)
                    seen_lessons.add(l['lesson'])
            
            # Format context
            current_context = format_rag_context(
                unique_similar[:3], 
                memories=unique_memories,
                lessons=unique_lessons[:3]
            )
            
            all_mems = unique_memories
            
        except Exception as e:
            print(f"[think] RAG retrieval skipped: {e}")
            current_context = "Error retrieving context."
            all_mems = []
    else:
        # Keep existing context
        all_mems = state.get('memory', [])
    
    # Run Thinker (ChainOfThought)
    result = thinker(
        message=task,
        history=history,
        memory=all_mems,
        rag_context=current_context
    )
    
    needs_code = result.needs_code
    tool_choice = getattr(result, 'tool_choice', 'none')
    
    # Tool safety check
    if tool_choice not in ("none", "") and state.get('tool_usage_count', 0) >= 3:
        print(f"[Thinker] Tool limit reached, ignoring tool choice {tool_choice}")
        tool_choice = "none"
        if not needs_code and not result.response:
            result.response = "I cannot process further tool requests due to loop limits."

    print(f"[think] needs_code={needs_code}, tool={tool_choice}")
    
    return {
        "thinking": result.thinking,
        "needs_code": needs_code,
        "tool_choice": tool_choice,
        "tool_args": result.tool_args,
        "citations": getattr(result, 'citations', []),
        "response": result.response if not needs_code and tool_choice == "none" else "",
        "rag_context": current_context,
        "memory": all_mems,
        # Reset execution state
        "files": {},
        "commands": [],
        "execution_logs": [],
        "execution_result": "",
        "retrieved_files": {},
        "reflections": [],
        "iteration": 0,
        "is_solved": (not needs_code and tool_choice == "none"),
    }


def tool_node(state: AgentState):
    """Executes a direct backend tool (SQL/RAG/File)."""
    tool_name = state.get("tool_choice", "none")
    tool_args = state.get("tool_args", "{}")
    
    print(f"[tool_node] Executing {tool_name} with args: {tool_args}")
    result = execute_tool(tool_name, tool_args)
    
    output = f"Tool '{tool_name}' result:\n{result}"
    count = state.get("tool_usage_count", 0) + 1
    
    return {
        "rag_context": output,
        "tool_choice": "none",
        "tool_usage_count": count
    }


def generate_code_node(state: AgentState):
    """Generates code files and commands."""
    task = state['task']
    code_plan = state.get('thinking', '')
    reflections = state.get('reflections', [])
    rag_context = state.get('rag_context', '')
    
    print(f"[generate_code] Reflections: {len(reflections)}, Context: {len(rag_context)} chars")
    
    result = code_generator(
        task=task, code_plan=code_plan,
        reflections=reflections, rag_context=rag_context
    )
    
    files = result.files if result.files else {}
    commands = result.commands if result.commands else []
    
    print(f"[generate_code] Files: {list(files.keys())}, Commands: {commands}")
    
    return {
        "files": files,
        "commands": commands,
        "iteration": state.get('iteration', 0) + 1,
    }


def execute_node(state: AgentState, config):
    """Executes commands in the sandbox and logs metrics."""
    files = state.get('files', {})
    commands = state.get('commands', [])
    start_time = time.time()
    
    log_callback = None
    if config and isinstance(config, dict):
        log_callback = config.get("configurable", {}).get("log_callback")
    
    thread_id = ""
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id", "")
    
    print(f"[execute] Files: {list(files.keys())}, Commands: {commands}")
    
    if not commands:
        return {
            "execution_logs": [{"timestamp": time.time(), "type": "error", "content": "No commands generated."}],
            "execution_result": "",
            "execution_error": "No commands generated.",
            "is_solved": False
        }
    
    result = sandbox.execute_batch(files, commands, on_log=log_callback)
    logs = result.get("logs", [])
    artifacts = result.get("artifacts", {})
    
    has_errors = False
    stdout_accum = []
    stderr_accum = []
    
    for log in logs:
        ltype = log['type']
        content = str(log.get('content', ''))
        
        if ltype == 'error':
            has_errors = True
            stderr_accum.append(content)
        elif ltype == 'stdout':
            stdout_accum.append(content)
        elif ltype == 'stderr':
            stderr_accum.append(content)
            if any(marker in content for marker in [
                'Traceback', 'Error:', 'IndentationError', 'SyntaxError',
                'NameError', 'TypeError', 'ValueError', 'ImportError',
                'ModuleNotFoundError', 'AttributeError', 'KeyError',
                'ZeroDivisionError', 'FileNotFoundError'
            ]):
                has_errors = True
    
    is_solved = not has_errors
    duration_ms = (time.time() - start_time) * 1000
    
    # Log metrics
    try:
        error_msg = "\n".join(stderr_accum)[:500] if stderr_accum else ""
        log_execution(
            task=state.get('task', '')[:500],
            success=is_solved,
            duration_ms=duration_ms,
            error_type="runtime_error" if has_errors else "",
            error_message=error_msg,
            iteration_count=state.get('iteration', 0),
            thread_id=thread_id
        )
    except Exception as e:
        print(f"[execute] Metrics logging skipped: {e}")
    
    print(f"[execute] is_solved={is_solved}, duration={duration_ms:.0f}ms, artifacts={list(artifacts.keys())}")
    
    return {
        "execution_logs": logs,
        "execution_result": "\n".join(stdout_accum),
        "execution_error": "\n".join(stderr_accum),
        "is_solved": is_solved,
        "retrieved_files": artifacts
    }


def reflect_node(state: AgentState):
    """Reflects on execution errors."""
    result = reflector(
        files=state.get('files', {}),
        commands=state.get('commands', []),
        execution_logs=state.get('execution_logs', [])
    )
    return {"reflections": [result.critique]}


def synthesize_node(state: AgentState):
    """Combines results into a response and stores solution."""
    task = state['task']
    thinking = state.get('thinking', '')
    execution_result = state.get('execution_result', '')
    files = state.get('files', {})
    
    result = synthesizer(
        message=task, code_plan=thinking,
        execution_output=execution_result, files=files,
        citations=state.get('citations', [])
    )
    
    # Store successful solution in RAG
    if state.get('is_solved', False) and files:
        try:
            code_str = "\n\n".join(f"# {f}\n{c}" for f, c in files.items())
            store_solution(task=task, code=code_str, result=execution_result[:2000])
        except Exception as e:
            print(f"[synthesize] RAG store skipped: {e}")
    
    return {"response": result.response}


def memory_node(state: AgentState):
    """Extracts and stores key facts."""
    task = state.get('task', '')
    response = state.get('response', '')
    existing_memories = state.get('memory', [])
    
    if not response or not task:
        return {}
        
    try:
        if memory_extractor:
            facts = memory_extractor(
                user_message=task,
                ai_response=response,
                existing_memory=existing_memories
            )
            for fact in facts:
                store_memory(fact)
            print(f"[memory] Stored {len(facts)} new facts")
    except Exception as e:
        print(f"[memory] Extraction failed: {e}")
        
    return {}


def lesson_node(state: AgentState):
    """Generates a self-improvement lesson and stores it."""
    task = state.get('task', '')
    response = state.get('response', '')
    execution_result = state.get('execution_result', '')
    
    if not task or not response:
        return {}
        
    try:
        if self_reflector:
            result = self_reflector(
                prompt=task,
                response=response,
                execution_output=execution_result
            )
            lesson = getattr(result, 'lesson', '')
            if lesson:
                store_lesson(task, response, lesson)
                print(f"[lesson] Stored self-improvement lesson")
                return {"reflection": lesson}
    except Exception as e:
        print(f"[lesson] Reflection failed: {e}")
        
    return {}

# ========== ROUTING ==========

def after_think(state: AgentState):
    if state.get('needs_code', False): return "generate_code"
    
    tool = state.get('tool_choice', 'none')
    if tool not in ("none", ""):
        if state.get('tool_usage_count', 0) >= 3:
            return "lesson"
        return "tool_node"
        
    return "lesson"

def after_execute(state: AgentState):
    if state.get('is_solved', False): return "synthesize"
    if state.get('iteration', 0) >= 3: return "synthesize"
    return "reflect"


# ========== BUILD GRAPH ==========

workflow = StateGraph(AgentState)

workflow.add_node("think", think_node)
workflow.add_node("tool_node", tool_node)
workflow.add_node("generate_code", generate_code_node)
workflow.add_node("execute", execute_node)
workflow.add_node("reflect", reflect_node)
workflow.add_node("synthesize", synthesize_node)
workflow.add_node("lesson", lesson_node)
workflow.add_node("memory", memory_node)

workflow.set_entry_point("think")

workflow.add_conditional_edges("think", after_think, {
    "generate_code": "generate_code",
    "tool_node": "tool_node",
    "lesson": "lesson",
})

workflow.add_edge("tool_node", "think")
workflow.add_edge("generate_code", "execute")

workflow.add_conditional_edges("execute", after_execute, {
    "synthesize": "synthesize",
    "reflect": "reflect",
})

workflow.add_edge("reflect", "generate_code")
workflow.add_edge("synthesize", "lesson") 
workflow.add_edge("lesson", "memory")
workflow.add_edge("memory", END)

if get_db_client() is not None:
    try:
        checkpointer = ClickHouseCheckpointer()
        app = workflow.compile(checkpointer=checkpointer)
        print("[Graph] Compiled with ClickHouse checkpointer")
    except Exception as e:
        print(f"[Graph] Checkpointer error: {e}")
        app = workflow.compile()
else:
    print("[Graph] ClickHouse offline — compiling without checkpointer")
    app = workflow.compile()
