# Ouroboros Architect: Recursive Self-Improving AI Agent

## Project Overview
The **Ouroboros Architect** is a cutting-edge AI system designed for the **Ruya 2026 Hackathon**. It represents a shift from static "chat" interfaces to dynamic, autonomous **Agentic AI**. The core mission is to engineer a system capable of **recursive self-refinement**—an agent that doesn't just execute code but actively learns from its mistakes, debugs its own errors, and improves its performance in real-time through metacognitive feedback loops.

This project implements "System 2" thinking in AI, enabling deliberate reasoning, self-critique, and iterative refinement, mimicking human expert workflows.

## Core Objectives
1.  **Autonomous Self-Correction**: Build an agent that can write code, run it, analyze failures (stack traces), and rewrite the code until it works.
2.  **Verifiable Improvement**: Quantify the agent's ability to recover from failure using a dedicated **Recovery Rate** metric.
3.  **Secure Execution**: Execute all generated code in a secure, sandboxed environment (E2B) to prevent harm and ensure reproducibility.
4.  **Strategic Alignment**: Align with the UAE's "AI-Powered UAE" and "Zero Government Bureaucracy" mandates by automating complex technical workflows.

## Technology Stack

The project leverages a modern, robust stack designed for agentic workflows:

### Orchestration & Logic
*   **LangGraph**: The backbone of the agent's orchestration. It manages the cyclic state graph, enabling the "Reflexion" loop where the agent can loop back to previous states based on execution results. It handles state persistence and conditional routing.
*   **DSPy (Declarative Self-improving Python)**: Used for **Dynamic Prompt Optimization**. Instead of brittle manual prompts, DSPy allows for programmable, optimizing prompts that improve over time. It structures the "cognitive" logic of the agent's nodes.
*   **Python**: The primary programming language for the agent and its logic.

### Environment & Execution
*   **E2B Code Interpreter SDK**: Provides secure, sandboxed cloud microVMs for executing the agent's generated code. This ensures isolation and captures standard output/error for the agent to analyze.
*   **Docker**: Likely used for containerization and consistent deployment verified by `test_docker.py`.

### User Interface
*   **Streamlit**: The frontend framework used to build the interactive dashboard. It visualizes the agent's thought process, code generation, execution logs, and the "Recovery Rate" metric.

### Data & Persistence
*   **Checkpointer**: Custom or LangGraph-integrated checkpointing to save and restore agent state.
*   **Vector Database / RAG**:  Likely used for retrieving context or documentation (implied by `src/rag.py` and `src/embeddings.py`).
*   **PostgreSQL / SQLite** (Implied): For persistent storage of traces or application state if needed (`src/db.py`).

## Architecture: The Multi-Agent Reflexion Pattern

The system architecture is a **Cybernetic Loop** consisting of specialized components:

1.  **AgentState**: A shared, immutable, typed state object (TypedDict) that passes data between nodes. It tracks the task, code solution, test cases, execution results, reflections, iteration count, and success status.

2.  **Nodes**:
    *   **Generator (The Actor)**: Uses DSPy to interpret the task and reflections to generate a code solution. It iterates on its approach based on past failures.
    *   **Sandbox (The Environment)**: A deterministic node that executes the code in the E2B sandbox. It captures exit codes, stdout, and stderr.
    *   **Reflector (The Critic)**: Analyzes the failure (stderr) from the Sandbox. It enables "metacognition" by diagnosing the error (syntax, logic, timeout) and adding a verbal critique to the `reflections` list in the state.
    *   **Test Generator**: Creates rigorous unit tests (assertions) from the initial prompt to define "success" objectively.

3.  **Workflow**:
    *   **Start** -> **Test Generator** -> **Generator** -> **Sandbox**
    *   **If Success (Exit Code 0)** -> **End**
    *   **If Failure** -> **Reflector** -> **Generator** (Loop continues until success or max iterations)

## Key Features
*   **Reflexion Loop**: A verbal reinforcement learning mechanism that uses natural language critiques instead of scalar rewards to guide improvement.
*   **Dynamic Prompting**: Automated optimization of system prompts using DSPy optimizers (BootstrapFewShot).
*   **Recovery Rate Metric**: A calculated percentage of how often the agent recovers from an initial failure to a successful solution.
    *   Formula: `(Failures Corrected / Total Initial Failures) * 100`
*   **Real-time Observability**: The Streamlit dashboard shows the "thinking" process, the code being written, and the live terminal output from the sandbox.

## Project Structure (Inferred)
*   **`app.py`**: Main Streamlit application entry point.
*   **`src/`**: Core source code.
    *   `graph.py`: LangGraph workflow definition.
    *   `dspy_modules.py`: DSPy signatures and modules for the Actor/Critic.
    *   `sandbox.py`: Interface for E2B Code Interpreter.
    *   `checkpointer.py`: State persistence logic.
    *   `rag.py`: RAG implementation for knowledge retrieval.
*   **`uploads/`**: Directory for user-uploaded documents (mostly PDFs) for RAG.
