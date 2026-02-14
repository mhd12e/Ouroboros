from typing import TypedDict, List, Dict, Any, Annotated
import operator

class AgentState(TypedDict):
    task: str
    history: List[Dict[str, str]]  # Conversation history
    memory: List[str]              # Short-term memory (key facts)
    
    # AI Thinking
    thinking: str                  # Verbose reasoning log
    needs_code: bool               # Whether code execution is needed
    tool_choice: str               # "sql_db", "rag_search", or "none"
    tool_args: str                 # JSON string arguments for the tool
    response: str                  # Final AI response text
    rag_context: str               # Retrieved RAG context from ClickHouse
    tool_results: str              # Output from direct tool execution
    tool_usage_count: int          # To prevent infinite tool loops


    
    # Code Execution (optional tool)
    files: Annotated[Dict[str, str], operator.ior]    
    commands: List[str]      
    execution_logs: Annotated[List[Dict[str, Any]], operator.add] 
    execution_result: str    
    execution_error: str     
    
    # Metadata & Citations
    citations: List[str]          # List of filenames used in the response
    retrieved_files: Dict[str, str] # Artifacts retrieved from the sandbox (name -> local path or content)
    reflection: str               # Lesson learned for self-improvement

    # Self-correction
    reflections: Annotated[List[str], operator.add]   
    iteration: int           
    is_solved: bool          
