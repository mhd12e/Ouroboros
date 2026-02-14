<div align="center">
  <img src="https://img.icons8.com/plasticine/200/snake.png" width="100" />
  <h1>🐍 Ouroboros</h1>
  <p><strong>The Recursive Self-Improving AI Architect</strong></p>
  <p><i>A project by <b>Organic Vision</b></i></p>

  [![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://www.python.org/)
  [![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
  [![DSPy](https://img.shields.io/badge/Cognition-DSPy-red?style=for-the-badge)](https://github.com/stanfordnlp/dspy)
  [![ClickHouse](https://img.shields.io/badge/Database-ClickHouse-yellow?style=for-the-badge&logo=clickhouse)](https://clickhouse.com/)
  [![AWS Bedrock](https://img.shields.io/badge/LLM-AWS_Bedrock-FF9900?style=for-the-badge&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
</div>

---

## 🚀 Overview

**Ouroboros** is a state-of-the-art Agentic AI system designed for autonomous problem-solving and self-evolution. Unlike traditional linear AI, Ouroboros implements a **cybernetic feedback loop** where the agent writes, executes, critiques, and learns from its own code in real-time.

Named after the ancient symbol of a snake eating its own tail, Ouroboros represents the pinnacle of **Recursive Self-Improvement**—an AI that doesn't just solve tasks, but actively learns how to solve them better next time.

## ✨ Key Features

- **🧠 System 2 Thinking**: Deep reasoning powered by **Claude 3.5 Sonnet** and **DSPy**'s Chain-of-Thought.
- **🔄 Reflexion Loop**: Autonomous debugging—the agent analyzes stack traces and self-corrects until victory.
- **📈 Self-Improvement**: A dedicated **Ouroboros Loop** that generates "lessons learned" after every task, storing them in RAG to avoid future mistakes.
- **📂 Multimodal RAG**: Instant knowledge retrieval from uploaded PDFs, Text, and Markdown files using **ClickHouse Vector Search**.
- **📦 Secure Sandboxing**: All code runs in isolated **Docker containers**, ensuring host safety and deterministic results.
- **🛰️ Long-term Memory**: Persistent state tracking and fact extraction using a high-performance **ClickHouse** backend.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) |
| **Cognition** | [DSPy](https://github.com/stanfordnlp/dspy) + AWS Bedrock (Claude 3.5 Sonnet) |
| **Database** | [ClickHouse](https://clickhouse.com/) (Vector Search + Metrics + Checkpoints) |
| **Embeddings** | Amazon Titan Text Embeddings v2 |
| **Sandbox** | Docker (Custom Python 3.12 Environment) |
| **Frontend** | [Streamlit](https://streamlit.io/) (Teal Native Theme) |

---

## 🏗️ Architecture

Ouroboros operates on a sophisticated state-graph logic that mimics human expert workflows:

```mermaid
graph TD
    User([User Prompt]) --> Think{Think Node}
    Think -->|Search Docs| Tool[Direct Tool Node]
    Tool --> Think
    Think -->|Needs Logic| Code[Generate Code]
    Code --> Exec[Sandbox Execution]
    Exec -->|Error| Reflect[Reflector Node]
    Reflect --> Code
    Exec -->|Success| Synth[Synthesizer Node]
    Synth --> Lesson[Self-Improvement Lesson]
    Lesson --> Mem[Memory Extraction]
    Mem --> Final((Final Response))
    
    style User fill:#14b8a6,stroke:#333,stroke-width:2px,color:#fff
    style Final fill:#14b8a6,stroke:#333,stroke-width:2px,color:#fff
    style Think fill:#f59e0b,stroke:#333,stroke-width:2px
    style Exec fill:#ef4444,stroke:#333,stroke-width:2px,color:#fff
    style Lesson fill:#8b5cf6,stroke:#333,stroke-width:2px,color:#fff
```

---

## 📥 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mhd12e/Ouroboros.git
   cd Ouroboros
   ```

2. **Environment Setup**:
   Create a `.env` file with your credentials:
   ```env
   AWS_ACCESS_KEY_ID=xxx
   AWS_SECRET_ACCESS_KEY=xxx
   AWS_REGION=us-east-1

   CLICKHOUSE_HOST=xxx.clickhouse.cloud
   CLICKHOUSE_PORT=8443
   CLICKHOUSE_USER=default
   CLICKHOUSE_PASSWORD=xxx
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Ouroboros**:
   ```bash
   streamlit run app.py
   ```

---

## 📁 Project Structure

```text
├── app.py                 # Streamlit UI (Chat, Files, MCP)
├── src/
│   ├── graph.py           # LangGraph state machine & logic
│   ├── cognition.py       # DSPy signatures & cognitive modules
│   ├── db.py              # ClickHouse connection & bootstrap
│   ├── rag.py             # Vector search & lesson retrieval
│   ├── sandbox.py         # Docker execution engine
│   ├── state.py           # AgentState definition
│   └── tools.py           # Direct backend tools (SQL/Files/RAG)
└── .gitignore             # The ultimate gitignore
```

---

<div align="center">
  <p>Built with ❤️ by <b>Organic Vision</b></p>
  <p><i>Empowering the next generation of Agentic AI.</i></p>
</div>
