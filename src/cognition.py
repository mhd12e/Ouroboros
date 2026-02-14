import dspy
import os
import json
import re
import ast
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIGURE DSPy WITH AWS BEDROCK ==========
lm = dspy.LM(
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    max_tokens=4096,
)
try:
    dspy.settings.configure(lm=lm)
    print("[Cognition] DSPy configured with AWS Bedrock — Claude 3.5 Sonnet v2")
except RuntimeError as e:
    print(f"[Cognition] DSPy already configured: {e}")

# ========== SIGNATURES ==========

class ThinkSignature(dspy.Signature):
    """You are an intelligent AI assistant with access to tools and memory.
    
    You have access to:
    1. A Python 3.12 sandbox for code execution (generate_code + execute)
    2. Direct backend tools (SQL, RAG, File Operations)
    3. Memory (short-term & long-term)
    
    DECISION PROCESS:
    1. Need Info? -> Use tools first (SQL, RAG, read_file, list_files).
    2. Need to Edit/Create? -> Use edit_file (precision edits) or write_file (new files).
    3. Need Computation? -> Set needs_code="yes" (Sandboxed execution).
    4. Have Solution? -> Respond directly (needs_code="no", tool_choice="none").
    
    DIRECT TOOLS (Bypass Sandbox):
    - "sql_db": Run SQL (e.g. {"query": "SELECT * FROM metrics"})
    - "rag_search": Find similar solutions (e.g. {"query": "how to add login"})
    - "search_documents": Search uploaded files (e.g. {"query": "project requirements"})
    - "read_file": Read file content (e.g. {"path": "src/app.py", "start_line": 10})
    - "edit_file": Replace text (e.g. {"path": "main.py", "old_text": "foo", "new_text": "bar"})
    - "write_file": Create/Overwrite file (e.g. {"path": "new.py", "content": "print('hi')"})
    - "list_files": Explore directory (e.g. {"path": ".", "max_depth": 2})
    - "run_command": Run shell command on host (e.g. {"command": "ls -l"})
    
    Set tool_choice="none" if no direct tool is needed.
    
    CITATIONS: If you use information from 'rag_search' or 'search_documents', you MUST list the filenames used in the 'citations' field.
    
    LESSONS: You also have access to 'lessons' in the rag_context. These are past reflections on how to improve. Follow them strictly.
    """
    message = dspy.InputField(desc="The user's current message.")
    history = dspy.InputField(desc="Previous conversation messages for context.")
    memory = dspy.InputField(desc="Key facts remembered from this session.")
    rag_context = dspy.InputField(desc="Context from direct tools (SQL/File results) OR similar past solutions/lessons.")
    thinking = dspy.OutputField(desc="Your detailed reasoning process. Explain why you chose a specific tool or approach.")
    needs_code = dspy.OutputField(desc='Must be exactly "yes" or "no". Use "yes" for sandboxed scripts, "no" for direct tools.')
    tool_choice = dspy.OutputField(desc='One of: "sql_db", "rag_search", "search_documents", "read_file", "edit_file", "write_file", "list_files", "run_command", "none".')
    tool_args = dspy.OutputField(desc='JSON arguments for the tool.')
    citations = dspy.OutputField(desc='JSON list of filenames used from rag_context (e.g. ["doc1.pdf"]).')
    code_plan = dspy.OutputField(desc='If needs_code is "yes": describe what code to write. If "no": write "N/A".')
    response = dspy.OutputField(desc='If needs_code is "no" and tool_choice is "none": your complete response in markdown.')


class ReflectSignature(dspy.Signature):
    """Analyze the prompt and the AI's response to provide constructive feedback.
    
    Identify how the response could have been better:
    - Missing details or edge cases
    - Better tool usage (e.g. could have used SQL instead of Python)
    - Code quality or efficiency
    - Clarity and formatting
    
    Provide a concise lesson: 'Next time, how will I do this in a better way?'
    """
    prompt = dspy.InputField(desc="The original user prompt.")
    response = dspy.InputField(desc="The AI's final response.")
    execution_output = dspy.InputField(desc="Raw output from tools/sandbox.")
    lesson = dspy.OutputField(desc="Next time, how will I do this in a better way?")


class ExtractMemorySignature(dspy.Signature):
    """Extract key facts from a conversation turn to remember for later.
    
    Extract ONLY important, reusable facts:
    - User preferences and constraints
    - Key results, numbers, or conclusions
    - Names, topics, or projects discussed
    - Decisions made or approaches chosen
    
    Do NOT extract conversational fluff or duplicates.
    """
    user_message = dspy.InputField(desc="What the user said.")
    ai_response = dspy.InputField(desc="What the AI responded.")
    existing_memory = dspy.InputField(desc="Facts already in memory (avoid duplicates).")
    new_facts = dspy.OutputField(desc='Newline-separated list of key facts. Write "NONE" if nothing worth remembering.')


class GenerateCodeSignature(dspy.Signature):
    """Generates code files and execution commands.
    
    RULES:
    1. Python 3.12 is PRE-INSTALLED. Do NOT use apt-get for stdlib modules.
    2. Only use pip if you need a third-party package.
    3. The script MUST print clear, labeled output to stdout.
    4. Pay extreme attention to Python indentation (4 spaces per level).
    
    CHECK RAG CONTEXT: If similar code has worked before, adapt it rather than starting from scratch.
    
    WHEN REFLECTIONS EXIST (fixing a bug):
    - Make the SMALLEST possible change to fix the issue.
    - Do NOT rewrite the entire script.
    
    Output each file using this EXACT marker format:
    --- FILE: analysis.py ---
    # your code here
    print("Result:", value)
    --- END FILE ---
    
    Output commands as a JSON list:
    ["python3 analysis.py"]
    """
    task = dspy.InputField(desc="The original user message.")
    code_plan = dspy.InputField(desc="What the code should do.")
    rag_context = dspy.InputField(desc="Similar past solutions — reuse what worked.")
    reflections = dspy.InputField(desc="Previous error reflections. If present, make MINIMAL fixes only.")
    files = dspy.OutputField(desc="Files in --- FILE: name --- / --- END FILE --- format.")
    commands = dspy.OutputField(desc='JSON list of commands: ["python3 analysis.py"]')


class SynthesizeSignature(dspy.Signature):
    """Synthesize a final response using code execution results.
    
    You ran code to get accurate data. Now write a clear, well-formatted response
    that incorporates the execution results. Present data naturally in markdown.
    Do NOT just dump raw output — interpret and present results meaningfully.

    CITATIONS: If documents from the knowledge base were used, list them at the end of your response 
    exactly like this: 
    Sources: [filename1], [filename2]
    """
    message = dspy.InputField(desc="The original user message.")
    code_plan = dspy.InputField(desc="What the code was supposed to do.")
    execution_output = dspy.InputField(desc="The stdout output from running the code.")
    files = dspy.InputField(desc="The code files that were executed.")
    citations = dspy.InputField(desc="List of source filenames used for this task.")
    response = dspy.OutputField(desc="Complete markdown response incorporating results and citations.")


class ReflectOnErrorSignature(dspy.Signature):
    """Analyzes code execution errors and provides a precise fix.
    
    Include:
    1. What the code was supposed to do
    2. The actual error
    3. Root cause
    4. The EXACT minimal code change needed
    """
    files = dspy.InputField(desc="Source code files.")
    commands = dspy.InputField(desc="Commands executed.")
    execution_logs = dspy.InputField(desc="Execution logs with errors.")
    critique = dspy.OutputField(desc="Error analysis with exact fix needed.")


# ========== MODULES ==========

class Thinker(dspy.Module):
    def __init__(self):
        super().__init__()
        # Use ChainOfThought for extensive reasoning as requested
        self.think = dspy.ChainOfThought(ThinkSignature)

    def forward(self, message, history, memory=None, rag_context=""):
        history_str = ""
        if history:
            for msg in history[-10:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    history_str += f"[{role}]: {content}\n"
        if not history_str:
            history_str = "No previous conversation."
        
        memory_str = "\n".join(f"• {f}" for f in memory) if memory else "No memories yet."
        rag_str = rag_context if rag_context else "No similar past solutions."
        
        try:
            result = self.think(
                message=message, history=history_str,
                memory=memory_str, rag_context=rag_str
            )
            
            needs_code = str(getattr(result, 'needs_code', 'no')).strip().lower()
            needs_code_bool = needs_code in ('yes', 'true', '1')
            
            thinking = getattr(result, 'thinking', '')
            tool_choice = str(getattr(result, 'tool_choice', 'none')).strip().lower()
            tool_args = getattr(result, 'tool_args', '{}')
            code_plan = getattr(result, 'code_plan', 'N/A')
            response = getattr(result, 'response', '')
            
            citations_raw = getattr(result, 'citations', '[]')
            citations = _parse_json_like(citations_raw, expected_type=list)
            
            print(f"[Thinker] needs_code={needs_code_bool}, tool={tool_choice}, citations={citations}")
            
            return dspy.Prediction(
                thinking=thinking,
                needs_code=needs_code_bool,
                tool_choice=tool_choice,
                tool_args=tool_args,
                citations=citations,
                code_plan=code_plan,
                response=response
            )
        except Exception as e:
            print(f"ERROR in Thinker: {e}")
            import traceback; traceback.print_exc()
            return dspy.Prediction(
                thinking=f"Error during thinking: {e}",
                needs_code=False,
                tool_choice="none",
                tool_args="{}",
                citations=[],
                code_plan="N/A",
                response="I encountered an error. Could you try rephrasing?"
            )


class MemoryExtractor(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.Predict(ExtractMemorySignature)
    
    def forward(self, user_message, ai_response, existing_memory=None):
        memory_str = "\n".join(existing_memory) if existing_memory else "Empty"
        try:
            result = self.extract(
                user_message=user_message,
                ai_response=ai_response[:2000],
                existing_memory=memory_str
            )
            raw = str(getattr(result, 'new_facts', 'NONE')).strip()
            if raw.upper() == 'NONE' or not raw:
                return []
            facts = [f.strip().lstrip('•-* ') for f in raw.split('\n') if f.strip() and f.strip().upper() != 'NONE']
            print(f"[MemoryExtractor] Extracted {len(facts)} new facts")
            return facts
        except Exception as e:
            print(f"ERROR in MemoryExtractor: {e}")
            return []


class CodeGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateCodeSignature)

    def forward(self, task, code_plan, reflections, rag_context=""):
        reflections_str = "\n".join(reflections) if reflections else "None"
        rag_str = rag_context if rag_context else "No similar past solutions."
        
        try:
            result = self.generate(
                task=task, code_plan=code_plan,
                rag_context=rag_str, reflections=reflections_str
            )
            rationale = getattr(result, "rationale", "")
            raw_files = str(result.files)
            
            files = _parse_file_blocks(raw_files)
            if not files:
                files = _parse_file_blocks(rationale)
            if not files:
                files = _parse_code_blocks_with_names(raw_files)
            if not files:
                files = _parse_code_blocks_with_names(rationale)
            if not files:
                files = _parse_json_like(raw_files, expected_type=dict)
            if not files and rationale:
                files = _parse_json_like(rationale, expected_type=dict)
            
            commands = _parse_commands(result.commands)
            if not commands and rationale:
                commands = _parse_commands(rationale)
            
            print(f"[CodeGenerator] Parsed {len(files)} files: {list(files.keys())}")
            print(f"[CodeGenerator] Parsed {len(commands)} commands: {commands}")
            return dspy.Prediction(files=files, commands=commands, rationale=rationale)
        except Exception as e:
            print(f"ERROR in CodeGenerator: {e}")
            import traceback; traceback.print_exc()
            return dspy.Prediction(files={}, commands=[], rationale="")


class Synthesizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.synthesize = dspy.ChainOfThought(SynthesizeSignature)
    
    def forward(self, message, code_plan, execution_output, files, citations=None):
        files_str = ""
        if isinstance(files, dict):
            for fname, content in files.items():
                files_str += f"\n--- {fname} ---\n{content}\n"
        else:
            files_str = str(files)
        
        citations_str = ", ".join(citations) if citations else "None"
        
        try:
            result = self.synthesize(
                message=message, code_plan=code_plan,
                execution_output=execution_output, files=files_str,
                citations=citations_str
            )
            return dspy.Prediction(
                response=result.response,
                rationale=getattr(result, "rationale", "")
            )
        except Exception as e:
            print(f"ERROR in Synthesizer: {e}")
            return dspy.Prediction(
                response=f"Code executed. Results:\n\n```\n{execution_output}\n```",
                rationale=""
            )


class SelfReflector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.reflect = dspy.ChainOfThought(ReflectSignature)

    def forward(self, prompt, response, execution_output):
        try:
            result = self.reflect(
                prompt=prompt, 
                response=response[:5000], 
                execution_output=str(execution_output)[:5000]
            )
            return dspy.Prediction(lesson=result.lesson)
        except Exception as e:
            print(f"ERROR in SelfReflector: {e}")
            return dspy.Prediction(lesson="Continue providing accurate and helpful responses.")


class Reflector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.reflect = dspy.ChainOfThought(ReflectOnErrorSignature)

    def forward(self, files, commands, execution_logs):
        files_str = ""
        if isinstance(files, dict):
            for fname, content in files.items():
                files_str += f"\n--- {fname} ---\n{content}\n"
        else:
            files_str = str(files)
        
        commands_str = json.dumps(commands) if isinstance(commands, list) else str(commands)
        
        if isinstance(execution_logs, list):
            important_logs = []
            for log in execution_logs:
                ltype = log.get('type', '')
                content = str(log.get('content', ''))
                if ltype in ('stdout', 'stderr') and any(skip in content for skip in [
                    'Reading package', 'Building dependency', 'Get:', 'Fetched',
                    'Selecting previously', 'Preparing to unpack', 'Unpacking',
                    'Setting up', 'Processing triggers', '(Reading database',
                ]):
                    continue
                important_logs.append(log)
            logs_str = json.dumps(important_logs, indent=2)
        else:
            logs_str = str(execution_logs)
        
        try:
            result = self.reflect(files=files_str, commands=commands_str, execution_logs=logs_str)
            rationale = getattr(result, "rationale", "")
            return dspy.Prediction(critique=result.critique, rationale=rationale)
        except Exception as e:
            print(f"ERROR in Reflector: {e}")
            return dspy.Prediction(critique=f"Error: {e}", rationale="")


# ========== PARSERS ==========

def _parse_file_blocks(text):
    if not isinstance(text, str):
        return {}
    files = {}
    pattern = r'---\s*(?:FILE|BEGIN FILE)[:\s]+(\S+)\s*---\s*\n(.*?)---\s*END FILE\s*---'
    matches = re.findall(pattern, text, re.DOTALL)
    for fname, content in matches:
        files[fname.strip()] = content.rstrip('\n')
    return files

def _parse_code_blocks_with_names(text):
    if not isinstance(text, str):
        return {}
    files = {}
    pattern = r'(?:\*\*|`|#{1,3}\s*)([\w][\w.\-/]*\.(?:py|js|ts|c|cpp|h|java|rb|go|rs|sh|txt|html|css))\s*(?:\*\*|`|)\s*\n\s*```\w*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    for fname, content in matches:
        files[fname.strip()] = content.rstrip('\n')
    return files

def _fix_json_newlines(text):
    result = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == '\\' and in_string and i + 1 < len(text):
            result.append(c)
            result.append(text[i + 1])
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        elif in_string and c == '\n':
            result.append('\\n')
            i += 1
            continue
        elif in_string and c == '\t':
            result.append('\\t')
            i += 1
            continue
        result.append(c)
        i += 1
    return ''.join(result)

def _parse_json_like(output, expected_type=None):
    if not isinstance(output, str):
        if output and expected_type and isinstance(output, expected_type):
            return output
        return output if output else ({} if expected_type == dict else [])
    
    text = output.strip()
    if not text:
        return {} if expected_type == dict else []
    
    code_blocks = re.findall(r"```(?:json|python|)?\s*(.*?)```", text, re.DOTALL)
    candidates = list(code_blocks) + [text]
    
    for block in candidates:
        block = block.strip()
        if not block:
            continue
        for parser in [json.loads, ast.literal_eval]:
            try:
                parsed = parser(block)
                if expected_type is None or isinstance(parsed, expected_type):
                    return parsed
            except:
                pass
        try:
            fixed = _fix_json_newlines(block)
            parsed = json.loads(fixed)
            if expected_type is None or isinstance(parsed, expected_type):
                return parsed
        except:
            pass
    
    if expected_type == dict:
        for m in re.finditer(r'\{', text):
            start, depth = m.start(), 0
            for i in range(start, len(text)):
                if text[i] == '{': depth += 1
                elif text[i] == '}': depth -= 1
                if depth == 0:
                    try:
                        candidate = _fix_json_newlines(text[start:i+1])
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except:
                        pass
                    break
    
    return {} if expected_type == dict else []

def _parse_commands(output):
    if isinstance(output, list):
        return [str(c) for c in output]
    if not isinstance(output, str) or not output.strip():
        return []
    
    text = output.strip()
    
    parsed = _parse_json_like(text)
    if isinstance(parsed, list):
        return [str(c) for c in parsed]
    if isinstance(parsed, dict):
        for k, v in parsed.items():
            if isinstance(v, list):
                return [str(c) for c in v]
    
    lines = re.findall(r'`([^`]+)`', text)
    if lines:
        return lines
    
    lines = re.findall(r'(?:^|\n)\s*(?:[-*]|\d+[.)])\s+(.+)', text)
    if lines:
        return [l.strip().strip('`"\'') for l in lines if l.strip()]
    
    cmd_prefixes = ['apt', 'pip', 'python', 'npm', 'node', 'gcc', 'g++', 'sh ', 'bash', 'cd ', 'mkdir', 'cat ', 'echo ', 'chmod', './', 'make']
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cmds = [l for l in lines if any(l.startswith(p) for p in cmd_prefixes)]
    if cmds:
        return cmds
    
    return []


# ========== NEW DSCPY MODULES ==========

class QuerySignature(dspy.Signature):
    """Generate improved search queries for RAG retrieval.
    
    Create 3 distinct search queries based on the user task:
    1. Keyword-focused (e.g. 'python dataframe merge')
    2. Semantic/Concept-focused (e.g. 'how to combine datasets')
    3. Error/Issue-focused (if applicable)
    """
    task = dspy.InputField(desc="User's task")
    history = dspy.InputField(desc="Conversation history")
    queries = dspy.OutputField(desc="List of 3 queries, one per line")


class QueryGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(QuerySignature)
        
    def forward(self, task, history):
        history_str = ""
        if history:
            for msg in history[-3:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                history_str += f"{role}: {content}\n"
        
        try:
            result = self.generate(task=task, history=history_str)
            raw = getattr(result, "queries", "")
            # Parse line-based list
            queries = [q.strip('- *') for q in raw.split('\n') if q.strip()]
            return queries[:3]
        except Exception as e:
            print(f"[QueryGenerator] Error: {e}")
            return [task] # Fallback to original task
