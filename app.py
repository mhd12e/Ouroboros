import streamlit as st
import os
import sys
import time
import html
import uuid
import pypdf

sys.path.append(os.getcwd())

from src.graph import app as workflow_app
from src.state import AgentState
from src.cognition import MemoryExtractor
from src.db_admin_tool import get_recovery_rate
from src.rag import store_document

memory_extractor = MemoryExtractor()

# Page Config
st.set_page_config(
    page_title="Ouroboros",
    page_icon="🐍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ========== THEME CSS ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
    
    .stApp { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    :root {
        --primary: #14b8a6; /* Teal-500 */
        --primary-dim: #14b8a622;
        --bg-main: #09090b;
        --bg-card: #18181b;
        --border: #27272a;
        --text-main: #fafafa;
        --text-muted: #a1a1aa;
    }
    
    .stApp, .main .block-container {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
    }
    
    /* Clean Cards */
    .element-container { margin-bottom: 0.5rem; }
    
    .stExpander {
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        background: var(--bg-card) !important;
    }
    
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.9em !important;
        color: var(--text-muted) !important;
        background: transparent !important;
    }

    /* Terminal */
    .terminal-box {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8em;
        background: #000000;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 12px;
        max-height: 300px;
        overflow-y: auto;
    }
    .term-line { display: flex; gap: 8px; margin-bottom: 2px; }
    .term-ts { color: #52525b; min-width: 60px; }
    .term-content { color: #d4d4d8; }
    .term-err { color: #f87171; }
    .term-cmd { color: var(--primary); }
    
    /* Header */
    .app-header {
        display: flex; align-items: center; gap: 12px;
        padding-bottom: 20px; border-bottom: 1px solid var(--border);
        margin-bottom: 24px;
    }
    .logo { font-size: 24px; }
    .app-title { font-weight: 600; font-size: 1.2em; color: var(--text-main); }
    .app-badge { 
        background: var(--primary-dim); color: var(--primary);
        font-size: 0.7em; padding: 2px 8px; border-radius: 12px;
        font-weight: 500; letter-spacing: 0.05em;
    }
    
    /* Custom Status */
    .status-badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 10px; border-radius: 4px;
        font-size: 0.75em; font-weight: 500;
        background: var(--bg-card); border: 1px solid var(--border);
        color: var(--text-muted);
    }
    .status-badge.active {
        border-color: var(--primary);
        color: var(--primary);
        background: var(--primary-dim);
    }
    
    .stChatInput > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== HEADER ==========
st.markdown("""
<div class="app-header">
    <div class="logo">🐍</div>
    <div class="app-title">Ouroboros</div>
    <div class="app-badge">BEDROCK · CLICKHOUSE · RAG</div>
</div>
""", unsafe_allow_html=True)

# ========== SESSION STATE ==========
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "execution_logs" not in st.session_state:
    st.session_state.execution_logs = []
if "generated_files" not in st.session_state:
    st.session_state.generated_files = {}
if "current_thinking" not in st.session_state:
    st.session_state.current_thinking = ""
if "current_status" not in st.session_state:
    st.session_state.current_status = "idle"
if "memory" not in st.session_state:
    st.session_state.memory = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# ========== LAYOUT ==========
tab_chat, tab_files, tab_mcp = st.tabs(["💬 Chat", "📂 Files", "🔌 MCP"])

with tab_chat:
    col_main, col_side = st.columns([2, 1], gap="large")
    
    # ========== RIGHT: STATUS & INSPECTOR (PLACEHOLDERS) ==========
    with col_side:
        # 1. Status
        status_ph = st.empty()
        st.divider()

        # 2. Live Reasoning
        st.caption("LIVE REASONING")
        thinking_ph = st.empty()
        st.divider()
        
        # 3. Terminal
        st.caption("TERMINAL")
        terminal_ph = st.empty()
        st.divider()
        
        # 4. Memory
        st.caption("MEMORY")
        memory_ph = st.empty()

        # Helper to render status
        def render_status(status):
            status_label = {
                "idle": "Ready",
                "thinking": "Reasoning...",
                "coding": "Writing Code...",
                "running": "Executing Tools...",
                "done": "Complete",
                "error": "Failed"
            }.get(status, "Processing")
            
            is_active = status not in ("idle", "done", "error")
            cls = "active" if is_active else ""
            
            status_ph.markdown(f"""
            <div class="status-badge {cls}">
                <span style="font-size:1.2em">{'⚡' if is_active else '•'}</span> {status_label}
            </div>
            """, unsafe_allow_html=True)

        # Helper to render thinking
        def render_thinking(text):
            if text:
                thinking_ph.code(text, language="text")
            else:
                thinking_ph.markdown('<span style="color:#52525b; font-style:italic;">Waiting for task...</span>', unsafe_allow_html=True)
                
        # Helper to render terminal
        def render_terminal(logs):
            if logs:
                log_html = []
                for l in logs[-15:]:
                    ts = time.strftime('%H:%M:%S', time.localtime(l['timestamp']))
                    content = html.escape(str(l['content']))
                    color_cls = "term-err" if l['type'] == 'error' else ("term-cmd" if l['type'] == 'command' else "term-content")
                    log_html.append(f'<div class="term-line"><span class="term-ts">{ts}</span><span class="{color_cls}">{content}</span></div>')
                terminal_ph.markdown(f'<div class="terminal-box">{"".join(log_html)}</div>', unsafe_allow_html=True)
            else:
                terminal_ph.markdown('<div class="terminal-box" style="color:#52525b">Ready for commands.</div>', unsafe_allow_html=True)

        # Helper to render memory
        def render_memory():
            if st.session_state.memory:
                 lines = [f"- {m}" for m in st.session_state.memory[-5:]]
                 memory_ph.markdown("\n".join(lines))
            else:
                memory_ph.markdown('<span style="color:#52525b">No long-term memories yet.</span>', unsafe_allow_html=True)

        # Initial Render
        render_status(st.session_state.current_status)
        render_thinking(st.session_state.current_thinking)
        render_terminal(st.session_state.execution_logs)
        render_memory()

    # ========== LEFT: CHAT ==========
    with col_main:
        chat_container = st.container()
        
        with chat_container:
            if not st.session_state.messages:
                st.markdown("""
                <div style="text-align: center; padding: 60px 0; color: #52525b;">
                    <div style="font-size: 40px; margin-bottom: 10px; opacity: 0.3;">🐍</div>
                    Ask anything. I'll write code, query data, and learn.
                    <br><br>
                </div>
                """, unsafe_allow_html=True)
            
            for msg in st.session_state.messages:
                role = msg["role"]
                if role == "user":
                    with st.chat_message("user", avatar="👤"):
                        st.write(msg["content"])
                else:
                    with st.chat_message("assistant", avatar="🐍"):
                        if msg.get("content"):
                            st.write(msg["content"])
                        
                        if msg.get("retrieved_files"):
                            cols = st.columns(len(msg["retrieved_files"]))
                            for i, (fname, fpath) in enumerate(msg["retrieved_files"].items()):
                                try:
                                    with open(fpath, "rb") as f:
                                        cols[i % len(cols)].download_button(
                                            label=f"💾 {fname}",
                                            data=f.read(),
                                            file_name=fname,
                                            key=f"dl_{msg.get('thinking', '')[:10]}_{fname}"
                                        )
                                except: pass

                        if msg.get("thinking"):
                            with st.expander("Reasoning", expanded=False):
                                st.markdown(f"```text\n{msg['thinking']}\n```")
                        
                        if msg.get("reflection"):
                            st.markdown(f"""
                            <div style="background-color:rgba(20, 184, 166, 0.05); border-left: 3px solid #14b8a6; padding: 15px; border-radius: 5px; margin-top: 20px;">
                                <div style="font-weight: 600; color: #14b8a6; margin-bottom: 5px; font-size: 0.9em;">
                                    🧠 HOW COULD OF I MADE BETTER?
                                </div>
                                <div style="font-size: 0.9em; color: #52525b; font-style: italic;">
                                    {msg['reflection']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        if msg.get("tool_use"):
                            t = msg["tool_use"]
                            with st.expander(f"Tool: {t['tool']}", expanded=False):
                                st.caption(f"Args: {t['args']}")
                                st.code(t['result'], language="json" if t['tool'] == "sql_db" else "text")
                        if msg.get("files"):
                            with st.expander(f"Generated Files ({len(msg['files'])})", expanded=False):
                                for fname, content in msg["files"].items():
                                    st.markdown(f"**{fname}**")
                                    st.code(content)
                        if msg.get("execution"):
                            with st.expander("Execution Output", expanded=False):
                                st.code(msg["execution"])
                        if msg.get("rag_context") and "No similar" not in msg["rag_context"]:
                            with st.expander("Context Retrieved", expanded=False):
                                st.text(msg["rag_context"])

        # Input
        if prompt := st.chat_input("Message Ouroboros...", disabled=st.session_state.processing):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.processing = True
            st.session_state.execution_logs = []
            st.session_state.generated_files = {}
            st.session_state.current_thinking = ""
            st.session_state.current_status = "thinking"
            st.rerun() # OK here, starts processing loop

# ========== EXECUTION LOOP ==========
if st.session_state.processing:
    # Prepare Input
    prompt = st.session_state.messages[-1]["content"]
    history = [
        {"role": m["role"], "content": m.get("content", "")} 
        for m in st.session_state.messages[:-1] 
        if m.get("content")
    ]
    
    initial_params = {
        "task": prompt,
        "history": history,
        "memory": list(st.session_state.memory),
        "thinking": "",
        "needs_code": False,
        "response": "",
        "rag_context": "",
        "files": {},
        "commands": [],
        "execution_logs": [],
        "execution_result": "",
        "execution_error": "",
        "reflections": [],
        "iteration": 0,
        "is_solved": False,
        "tool_usage_count": 0,
    }
    
    def stream_log_callback(entry):
        st.session_state.execution_logs.append(entry)
        render_terminal(st.session_state.execution_logs)

    try:
        config = {
            "configurable": {
                "log_callback": stream_log_callback,
                "thread_id": st.session_state.thread_id,
            }
        }
        current_state = initial_params.copy()
        
        # We iterate the graph stream
        for event in workflow_app.stream(current_state, config=config):
            for node_name, node_output in event.items():
                
                # --- STATE UPDATES (IN-PLACE) ---
                if node_name == "think":
                    thinking = node_output.get("thinking", "")
                    st.session_state.current_thinking = thinking
                    st.session_state.current_status = "coding" if node_output.get("needs_code") else "thinking"
                    
                    # Update Placeholders
                    render_thinking(thinking)
                    render_status(st.session_state.current_status)
                
                elif node_name == "tool_node":
                    st.session_state.current_status = "running"
                    render_status("running")
                    
                    tool_use = {
                        "tool": current_state.get("tool_choice"),
                        "args": current_state.get("tool_args"),
                        "result": node_output.get("rag_context")
                    }
                    
                    # Render tool usage immediately in chat container
                    with chat_container:
                        with st.chat_message("assistant", avatar="🐍"):
                            with st.expander(f"Tool: {tool_use['tool']}", expanded=True): # Expand live tools
                                st.caption(f"Args: {tool_use['args']}")
                                st.code(tool_use['result'], language="json" if tool_use['tool'] == "sql_db" else "text")

                elif node_name == "generate_code":
                    files = node_output.get("files", {})
                    if files:
                         st.session_state.generated_files.update(files)
                    st.session_state.current_status = "running"
                    render_status("running")

                elif node_name == "synthesize":
                     st.session_state.current_status = "done"
                     render_status("done")

                # --- MERGE STATE ---
                if not node_output: continue
                for k, v in node_output.items():
                    if k == "files" and isinstance(v, dict):
                        current_state["files"].update(v)
                    elif k == "retrieved_files" and isinstance(v, dict):
                        current_state["retrieved_files"] = v # Take latest
                    elif k in ("execution_logs", "reflections", "citations") and isinstance(v, list):
                        current_state[k] = (current_state.get(k) or []) + v
                    elif k == "reflection":
                        current_state[k] = v
                    else:
                        current_state[k] = v

        # Final Response
        final_msg = {
            "role": "assistant",
            "content": current_state.get("response", "Done."),
            "thinking": current_state.get("thinking"),
            "files": current_state.get("files"),
            "execution": current_state.get("execution_result"),
            "rag_context": current_state.get("rag_context"),
            "retrieved_files": current_state.get("retrieved_files"),
            "citations": current_state.get("citations"),
            "reflection": current_state.get("reflection")
        }
        
        st.session_state.messages.append(final_msg)
        
        # Memory Extraction
        try:
             new_facts = memory_extractor(
                 user_message=prompt,
                 ai_response=final_msg["content"],
                 existing_memory=st.session_state.memory
             )
             if new_facts:
                 st.session_state.memory.extend(new_facts)
                 st.session_state.memory = st.session_state.memory[-50:]
        except: pass
        
        st.session_state.processing = False
        st.session_state.current_status = "idle"
        st.rerun()

    except Exception as e:
        import traceback
        st.error(f"Error: {e}")
        st.code(traceback.format_exc())
        st.session_state.processing = False
        st.session_state.current_status = "error"
        render_status("error")

# ========== FILES TAB ==========
with tab_files:
    st.header("📂 Documents")
    st.caption("Upload PDFs or Text files to the Knowledge Base.")
    
    uploaded_files = st.file_uploader("Drop files here", accept_multiple_files=True)
    if st.button("Upload & Index", type="primary") and uploaded_files:
        if not os.path.exists("uploads"): os.makedirs("uploads")
        
        progress = st.progress(0)
        for i, file in enumerate(uploaded_files):
            try:
                path = os.path.join("uploads", file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                
                # PDF/Text Logic
                content = ""
                if file.name.lower().endswith(".pdf"):
                    reader = pypdf.PdfReader(file)
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            content += extracted + "\n"
                else:
                    content = file.getvalue().decode("utf-8", errors="replace")
                
                if content.strip():
                     store_document(file.name, content)
            except Exception as e:
                st.error(f"Error processing {file.name}: {e}")
            
            progress.progress((i+1)/len(uploaded_files))
            
        st.success("Indexed successfully!")
        time.sleep(1)
        st.rerun()
    
    if os.path.exists("uploads"):
        st.markdown("### Library")
        files = os.listdir("uploads")
        if not files:
            st.info("No files uploaded.")
        else:
            for f in files:
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"📄 `{f}`")
                with c2:
                    if st.button("🗑️", key=f"del_{f}", help="Delete file"):
                        os.remove(os.path.join("uploads", f))
                        st.toast(f"Deleted {f}")
                        time.sleep(0.5)
                        st.rerun()

# ========== MCP TAB ==========
with tab_mcp:
    st.header("🔌 MCP Connect")
    st.caption("Model Context Protocol - Extend Agent Capabilities")
    
    st.info("🔗 Connect to MCP Servers to give Ouroboros access to external tools (GitHub, Slack, PostgreSQL, etc.)")
    
    with st.expander("Add New Server", expanded=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.text_input("Server URL", placeholder="ws://localhost:8000/mcp", key="mcp_url")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Connect Server", type="primary"):
                st.toast("MCP Support Coming Soon!", icon="🚧")
                
    st.markdown("### Active Servers")
    st.markdown("""
    <div style="text-align:center; padding: 40px; color: #52525b; border: 1px dashed #27272a; border-radius: 8px;">
        No active MCP connections.
    </div>
    """, unsafe_allow_html=True)
