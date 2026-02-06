<!-- This is the documentation for this codebase. Read this carefully before making changes. Claude will use this file. -->

# Multi-Agent Supervisor Architecture - Complete Documentation

**Version:** 2.0.0
**Date:** 2026-02-06
**Pattern:** LangGraph Multi-Agent Supervisor
**Status:** ✅ Production-Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Data Flow](#data-flow)
5. [Installation & Setup](#installation--setup)
6. [Usage](#usage)
7. [Customization](#customization)
8. [File Structure](#file-structure)
9. [Best Practices](#best-practices)
10. [References](#references)

---

## Overview

### What is This?

A **production-ready multi-agent orchestrator** that coordinates specialist agents to answer complex queries by combining:

- **SQL data** from Databricks Unity Catalog via Genie
- **Document knowledge** from uploaded PDFs/DOCX via RAG
- **Intelligent routing** via supervisor agent
- **Synthesis** of results from multiple sources
- **Replanning** when initial approaches fail
- **Human-in-loop** for clarification when stuck

### Key Features

✅ **Multi-Agent Supervisor Pattern** - Central orchestrator coordinates specialists
✅ **Databricks Genie Integration** - Natural language to SQL on Unity Catalog
✅ **Agentic RAG** - Intelligent document retrieval with FAISS
✅ **Conversation Memory** - Maintains context across questions
✅ **Replanning & Iteration** - Retries with different approaches on failure
✅ **Human-in-Loop** - Asks for clarification after 5 iterations
✅ **Clean Architecture** - 401 lines of agent code (vs 3,110 originally)
✅ **Minimal Dependencies** - 16 core packages (vs 30+ originally)

### Design Philosophy

**Use Libraries, Don't Build Them**

This implementation follows Databricks and LangChain best practices:

- ✅ Use `LangGraph StateGraph` for orchestration (not custom)
- ✅ Use `databricks_langchain.GenieAgent` (not custom Genie wrapper)
- ✅ Use LangChain `create_retriever_tool` (not custom RAG)
- ✅ Use `FAISS` directly (not custom vector store wrapper)
- ✅ Use `MemorySaver` for checkpointing (not custom memory)

**Result:** 89% less code, production-ready, maintainable.

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER QUESTION                          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
         ┌─────────────────────────────┐
         │   SUPERVISOR AGENT          │
         │   (Orchestrator)            │
         │                             │
         │  - Analyzes question        │
         │  - Routes to specialists    │
         │  - Replans if needed        │
         │  - Tracks iterations        │
         └──────────┬──────────────────┘
                    │
         ┌──────────┼────────────┬─────────────┐
         │          │            │             │
         ↓          ↓            ↓             ↓
    ┌────────┐ ┌───────────┐ ┌────────┐ ┌──────────┐
    │  SQL   │ │ Document  │ │ HUMAN  │ │ SYNTHESIS│
    │Special.│ │  Search   │ │ Loop   │ │  Agent   │
    └───┬────┘ └─────┬─────┘ └────┬───┘ └────┬─────┘
        │            │            │           │
        │            │            │           │
        └────────────┴────────────┴───────────┘
                       ↓
                 FINAL ANSWER
```

### LangGraph StateGraph

```python
# Core pattern
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SQL_Specialist", ToolNode([genie_tool]))
workflow.add_node("document_search", ToolNode([rag_tool]))
workflow.add_node("synthesis", synthesis_node)
workflow.add_node("human", human_node)

# Set entry point
workflow.set_entry_point("supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    {
        "synthesis": "synthesis",
        "human": "human",
        "SQL_Specialist": "SQL_Specialist",
        "document_search": "document_search",
    }
)

# Specialists loop back to supervisor
workflow.add_edge("SQL_Specialist", "supervisor")
workflow.add_edge("document_search", "supervisor")

# Terminal nodes
workflow.add_edge("synthesis", END)
workflow.add_edge("human", END)

# Compile with memory
graph = workflow.compile(checkpointer=MemorySaver())
```

### State Management

```python
class AgentState(TypedDict):
    """State passed between agents"""
    messages: Annotated[list[BaseMessage], operator.add]  # Accumulates
    next_agent: str           # Routing decision
    iterations: int           # Loop prevention
    final_answer: str         # Synthesized result
```

**Key Points:**
- `messages` uses `operator.add` - automatically accumulates across nodes
- `next_agent` controls routing ("FINISH", "HUMAN", "SQL_Specialist", "document_search")
- `iterations` prevents infinite loops (max 5)
- `final_answer` populated by synthesis agent

---

## Components

### 1. Supervisor Agent (Orchestrator)

**File:** `src/agent.py::create_supervisor_agent()`

**Role:** Central brain that coordinates all specialist agents.

**Capabilities:**
- Analyzes user questions and determines intent
- Routes to appropriate specialist(s) sequentially
- Can call multiple specialists (SQL first, then documents, then synthesis)
- Replans if results are insufficient
- Asks human for help after 5 iterations
- Decides when to finish and synthesize

**System Prompt:**
```python
"""You are a supervisor agent coordinating a team of specialists:

AVAILABLE SPECIALISTS:
- SQL_Specialist
- document_search

YOUR ROLE:
1. Analyze user questions
2. Route to appropriate specialist(s)
3. Replan if results are insufficient
4. Synthesize final answers
5. Ask HUMAN for clarification when needed

ROUTING RULES:
- For data/SQL queries → SQL_Specialist
- For document/policy questions → document_search
- If unsure or need clarification → HUMAN
- When you have complete answer → FINISH

IMPORTANT:
- You can call multiple specialists
- You can replan and retry
- Always synthesize results clearly
- Cite sources
- If stuck after 3 iterations → ask HUMAN

Respond with ONLY the next agent name: FINISH, SQL_Specialist, document_search, HUMAN"""
```

---

### 2. SQL Specialist (Genie Agent)

**File:** `src/agent.py::create_genie_agent()`

**Role:** Executes natural language SQL queries on Unity Catalog via Databricks Genie.

**Implementation:**
```python
def create_genie_agent():
    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    genie_tool = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="SQL_Specialist",
        description=f"""SQL query specialist. Use ONLY for:
        - Querying sales, revenue, transaction data
        - Customer analytics and demographics
        - Product performance and inventory

        Available tables: {', '.join(config.databricks.unity_tables)}
        Returns: Query results as markdown tables""",
        client=workspace_client,  # Proper authentication
        return_pandas=False,       # Return markdown strings
    )
    return genie_tool
```

---

### 3. Document Search Specialist (RAG Agent)

**File:** `src/agent.py::create_rag_agent()`

**Role:** Retrieves relevant information from uploaded documents.

**Implementation:**
```python
def create_rag_agent():
    # Load documents from directory
    docs = load_documents_from_directory("./data/documents")

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    splits = text_splitter.split_documents(docs)

    # Create FAISS vector store
    embeddings = AzureOpenAIEmbeddings(...)
    vectorstore = FAISS.from_documents(splits, embeddings)

    # Create retriever tool
    rag_tool = create_retriever_tool(
        vectorstore.as_retriever(search_kwargs={"k": 5}),
        "document_search",
        """Document search specialist. Use ONLY for:
        - Company policies, procedures
        - Technical documentation
        - Reference materials from PDFs/DOCX"""
    )
    return rag_tool
```

**Supported Formats:** PDF, DOCX, TXT, CSV, XLSX, PPTX

---

### 4. Synthesis Agent

**File:** `src/agent.py::create_synthesis_agent()`

**Role:** Combines results from multiple specialists into coherent final answer.

**Implementation:**
```python
def create_synthesis_agent():
    model = AzureChatOpenAI(..., temperature=0.3)

    system_prompt = """You are a synthesis specialist. Your job is to:
    1. Combine results from multiple agents
    2. Create a coherent, comprehensive answer
    3. Cite all sources clearly
    4. Format nicely for the user"""

    def synthesis_node(state: AgentState):
        response = model.invoke([
            SystemMessage(content=system_prompt),
            *state["messages"],
            HumanMessage(content="Please synthesize the above information into a final answer.")
        ])

        return {
            "messages": [response],
            "final_answer": response.content,
            "next_agent": "FINISH"
        }

    return synthesis_node
```

---

### 5. Human-in-Loop Agent

**File:** `src/agent.py::create_human_node()`

**Role:** Asks user for clarification when supervisor is stuck.

**Triggered When:**
- Supervisor is unsure how to route
- After 5 iterations without resolution
- Supervisor explicitly routes to "HUMAN"

**Production Customization:**

Replace with real human interaction:

```python
def create_human_node():
    def human_node(state: AgentState):
        # Option 1: Webhook
        response = requests.post("https://your-api.com/ask-human", ...)

        # Option 2: Queue system
        queue.publish("human-input-needed", ...)

        # Option 3: Slack/Teams integration
        slack.send_message(channel="agent-questions", ...)

        return {
            "messages": [HumanMessage(content=clarification)],
            "next_agent": "supervisor"
        }

    return human_node
```

---

## Data Flow

### Example 1: Simple SQL Query

**Question:** "What were our top 5 products by revenue last quarter?"

```
Step 1: User asks question
  ↓
Step 2: Supervisor analyzes → Routes to SQL_Specialist
  ↓
Step 3: SQL_Specialist executes
  - Calls Genie with question
  - Returns top 5 products with revenue
  ↓
Step 4: Supervisor reviews → Routes to Synthesis
  ↓
Step 5: Synthesis creates final answer with sources
  ↓
Step 6: User receives answer
  Iterations: 2, Latency: ~8s
```

---

### Example 2: Multi-Agent Coordination

**Question:** "Compare our Q4 sales performance against company policy targets"

```
Step 1: Supervisor → SQL_Specialist (get Q4 sales)
Step 2: Supervisor → document_search (get policy targets)
Step 3: Supervisor → Synthesis (combine both)
Step 4: User receives comprehensive answer
  Iterations: 4, Latency: ~12s
```

---

### Example 3: Replanning After Failure

**Question:** "What is our customer churn rate?"

```
Iteration 1: SQL_Specialist fails (no churn_rate column)
Iteration 2: Supervisor replans → Calculate from activity data
Iteration 3: Synthesis creates final answer
  Total iterations: 3
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Azure OpenAI account with GPT-4o access
- Databricks workspace with Unity Catalog and Genie Space

### Installation Steps

```bash
# 1. Clone repository
git clone <repository-url>
cd Langgraph-MultiAgent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Add documents (optional)
mkdir -p data/documents
cp your-docs/*.pdf data/documents/

# 5. Validate setup
python validate_setup.py

# 6. Run
python src/main.py
```

### Environment Configuration

Edit `.env` file:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Databricks
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_SQL_WAREHOUSE_ID=abc123...
GENIE_SPACE_ID=01234567...
UNITY_CATALOG_TABLES=sales_data,customer_data,product_data

# LLM Settings (optional)
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

---

## Usage

### CLI Usage

```bash
python src/main.py
```

**Example Session:**
```
================================================================================
Multi-Agent Orchestrator (Supervisor + Specialists)
================================================================================

✅ Multi-agent system initialized

💬 Ask me anything! (type 'exit' to quit)

🤔 You: What were our top 5 products by revenue?

✨ Answer:
Based on the sales data, here are the top 5 products by revenue:
1. Product A - $1.2M
2. Product B - $980K
...
```

### Python API Usage

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent
import uuid

# Initialize agent
agent = get_agent()

# Simple query
result = agent.invoke({
    "messages": [HumanMessage(content="What were top 5 products?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

print(result["final_answer"])

# Query with conversation memory
thread_id = str(uuid.uuid4())

result1 = agent.invoke(
    {
        "messages": [HumanMessage(content="What were Q4 sales?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)

# Follow-up (remembers Q4 context)
result2 = agent.invoke(
    {
        "messages": [HumanMessage(content="How does that compare to Q3?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)
```

---

## Customization

### Add New Specialist Agent

**Example: Web Search Specialist**

```python
# 1. Create specialist function (in src/agent.py)
def create_web_search_agent():
    from langchain_community.tools import DuckDuckGoSearchRun
    search_tool = DuckDuckGoSearchRun()

    return create_retriever_tool(
        search_tool,
        "web_search",
        """Web search specialist. Use for current events and external information."""
    )

# 2. Add to create_multi_agent_graph()
def create_multi_agent_graph():
    # Create new specialist
    web_agent = create_web_search_agent()
    agents = [genie_agent, rag_agent, web_agent]

    # Add as node
    workflow.add_node("web_search", ToolNode([web_agent]))

    # Update routing
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"web_search": "web_search", ...}
    )

    # Route back to supervisor
    workflow.add_edge("web_search", "supervisor")

# 3. Update supervisor system prompt
# Add: "For current events/external info → web_search"
```

---

## File Structure

```
Langgraph-MultiAgent/
├── src/
│   ├── agent.py                    # 401 lines - Complete multi-agent system
│   ├── main.py                     # 114 lines - CLI interface
│   ├── core/
│   │   └── config.py               # Configuration (Pydantic)
│   ├── utils/
│   │   ├── embeddings.py           # Azure OpenAI embeddings
│   │   ├── parsers.py              # Document parsers
│   │   └── logging.py              # Structured logging
│   └── services/
│       └── mlflow_tracker.py       # Optional observability
├── data/
│   └── documents/                  # Place PDFs, DOCX here
├── requirements.txt                # 37 lines - Minimal dependencies
├── validate_setup.py               # Setup validation
├── CLAUDE.md                       # This file - Main documentation
├── SKILLS.md                       # System capabilities
├── REFERENCE.md                    # API reference & examples
└── README.md                       # Quick start guide
```

---

## Best Practices

### 1. Question Formulation

**Good Questions:**
- "What were our top 5 products by revenue in Q4 2025?"
- "Compare Q4 sales performance against company policy targets"

**Poor Questions:**
- "Give me data" (too vague)
- "What happened?" (needs context)

### 2. Document Organization

```
data/documents/
├── policies/
│   └── sales_policy_2025.pdf
├── reports/
│   └── Q4_2025_analysis.pdf
└── technical/
    └── api_documentation.pdf
```

### 3. Conversation Memory

**Use thread_id for:**
- Multi-turn conversations
- Follow-up questions

**Don't use thread_id for:**
- Independent queries
- Different users

---

## References

### Official Documentation

- **LangGraph:** https://langchain-ai.github.io/langgraph/
- **LangGraph Multi-Agent:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/
- **Databricks Genie:** https://docs.databricks.com/generative-ai/agent-framework/multi-agent-genie
- **databricks-langchain:** https://pypi.org/project/databricks-langchain/
- **Azure OpenAI:** https://learn.microsoft.com/en-us/azure/ai-services/openai/

### Blog Posts & Guides

- **Multi-Agent Supervisor Pattern:** https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale
- **Agentic RAG:** https://docs.langchain.com/oss/python/langgraph/agentic-rag

---

## Troubleshooting

### Common Issues

**1. Import Error: GenieAgent**
```
Error: cannot import name 'GenieAgent'
```
**Solution:** Update databricks-langchain:
```bash
pip install databricks-langchain>=0.14.0
```

**2. Databricks Authentication Failed**
```
Error: Failed to initialize Databricks client
```
**Solution:** Check .env variables (DATABRICKS_HOST, DATABRICKS_TOKEN)

**3. No Documents Found**
```
Warning: No documents found - RAG agent not available
```
**Solution:** Add documents to `data/documents/`

### Debug Mode

```bash
export LOG_LEVEL=DEBUG
python src/main.py
```

---

## Next Steps

1. **Read REFERENCE.md** for detailed API documentation
2. **Read SKILLS.md** for system capabilities
3. **Run validate_setup.py** to ensure configuration
4. **Try the CLI** with your own questions
5. **Customize** by adding new specialist agents

---

**Version:** 2.0.0
**Date:** 2026-02-06
**Status:** ✅ Production-Ready
**Commit:** Latest on `claude/setup-docs-and-tests-vtX1W`
