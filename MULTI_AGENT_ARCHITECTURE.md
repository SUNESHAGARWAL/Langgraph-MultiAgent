# Multi-Agent Supervisor Architecture

**Version:** 2.0.0
**Date:** 2026-02-06
**Pattern:** LangGraph Multi-Agent Supervisor
**Status:** ✅ Production-Ready

---

## 🎯 Overview

This implements a **Multi-Agent Supervisor Architecture** where:

1. **Supervisor Agent** (Orchestrator) coordinates specialist agents
2. **Specialist Agents** handle domain-specific tasks
3. **Synthesis Agent** combines results from multiple specialists
4. **Human-in-Loop** asks for clarification when stuck
5. **Iterative Planning** enables replanning and retries

---

## 🏗️ Architecture Diagram

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

---

## 📋 Components

### 1. **Supervisor Agent** (Brain)

**File:** `src/agent.py::create_supervisor_agent()`

**Role:** Central orchestrator that coordinates all specialists

**Capabilities:**
- Analyzes user questions
- Routes to appropriate specialist(s)
- Can call multiple specialists sequentially
- Replans if results are insufficient
- Asks human if stuck after 5 iterations
- Decides when to finish and synthesize

**System Prompt:**
```
You are a supervisor agent coordinating a team of specialists:
- SQL_Specialist (for data queries)
- document_search (for documents)

Routing rules:
- Data/SQL → SQL_Specialist
- Documents → document_search
- Unsure → HUMAN
- Complete → FINISH
```

**State Management:**
```python
class AgentState(TypedDict):
    messages: list[BaseMessage]  # Conversation history
    next_agent: str              # Which agent to call next
    iterations: int              # Iteration counter (prevents loops)
    final_answer: str            # Synthesized final answer
```

---

### 2. **SQL Specialist** (Genie Agent)

**File:** `src/agent.py::create_genie_agent()`

**Role:** Executes SQL queries on Unity Catalog via Databricks Genie

**Capabilities:**
- Natural language to SQL conversion
- Query execution on Unity Catalog
- Returns results as markdown tables

**Tool Description:**
```
SQL query specialist. Use ONLY for:
- Querying sales, revenue, transaction data
- Customer analytics and demographics
- Product performance and inventory
- Any data/analytics questions requiring SQL

Available tables: sales_data, customer_data, product_data
Returns: Query results as markdown tables
```

**Implementation:**
```python
genie_tool = GenieAgent(
    genie_space_id=config.databricks.genie_space_id,
    genie_agent_name="SQL_Specialist",
    description="...",
    client=workspace_client,
    return_pandas=False,
)
```

---

### 3. **Document Search Specialist** (RAG Agent)

**File:** `src/agent.py::create_rag_agent()`

**Role:** Retrieves relevant information from uploaded documents

**Capabilities:**
- Semantic search over documents
- Retrieves top-k relevant chunks
- Returns document excerpts with sources

**Tool Description:**
```
Document search specialist. Use ONLY for:
- Company policies, procedures, guidelines
- Technical documentation and manuals
- Reference materials from uploaded PDFs/DOCX
- Knowledge base articles

Do NOT use for real-time data or analytics.
Returns: Relevant document excerpts with sources
```

**Implementation:**
```python
# Load documents from data/documents/
docs = load_documents_from_directory("./data/documents")

# Create FAISS vector store
vectorstore = FAISS.from_documents(splits, embeddings)

# Create retriever tool
rag_tool = create_retriever_tool(
    vectorstore.as_retriever(search_kwargs={"k": 5}),
    "document_search",
    "..."
)
```

---

### 4. **Synthesis Agent**

**File:** `src/agent.py::create_synthesis_agent()`

**Role:** Combines results from multiple specialists into coherent answer

**Capabilities:**
- Merges SQL results and document excerpts
- Creates comprehensive final answer
- Cites all sources
- Formats nicely for users

**System Prompt:**
```
You are a synthesis specialist. Your job is to:
1. Combine results from multiple agents
2. Create a coherent, comprehensive answer
3. Cite all sources clearly
4. Format nicely for the user

When synthesizing:
- Combine SQL results and document excerpts
- Highlight key findings
- Use markdown formatting
- Always cite sources
- Be concise but complete
```

**Temperature:** 0.3 (lower for consistency)

---

### 5. **Human-in-Loop Agent**

**File:** `src/agent.py::create_human_node()`

**Role:** Asks user for clarification when stuck

**Triggered when:**
- Supervisor is unsure how to route
- After 5 iterations without resolution
- When supervisor explicitly routes to HUMAN

**Customization Point:**
In production, replace with:
- Webhook to notify user
- Queue system
- Slack/Teams integration
- Email notification

---

## 🔄 Execution Flow

### Example: "What were top 5 products by revenue last quarter?"

```
Step 1: User asks question
  ↓
Step 2: Supervisor analyzes
  - Recognizes data/analytics question
  - Routes to SQL_Specialist
  ↓
Step 3: SQL_Specialist executes
  - Calls Genie with question
  - Gets SQL + results
  - Returns to Supervisor
  ↓
Step 4: Supervisor reviews results
  - Determines answer is sufficient
  - Routes to Synthesis
  ↓
Step 5: Synthesis creates final answer
  - Formats results
  - Cites source (sales_data table)
  - Returns to user
  ↓
Step 6: User receives answer
  Iterations: 2
```

### Example: Complex question requiring multiple specialists

```
Question: "Compare our Q4 sales performance against the company policy targets"

Step 1: Supervisor → SQL_Specialist
  - Gets Q4 sales data

Step 2: Supervisor → document_search
  - Retrieves policy document with targets

Step 3: Supervisor → Synthesis
  - Combines sales data + policy targets
  - Creates comparison
  - Cites both sources

Final answer: Complete comparison
Iterations: 3
```

### Example: Replanning when stuck

```
Question: "What is our customer churn rate?"

Step 1: Supervisor → SQL_Specialist
  - Queries customer_data table
  - Result: "No churn_rate column found"

Step 2: Supervisor → SQL_Specialist (replan)
  - Tries different approach
  - Calculates churn from customer activity
  - Result: Churn rate calculated

Step 3: Supervisor → Synthesis
  - Formats answer
  - Explains calculation method

Final answer: Churn rate with explanation
Iterations: 3
```

---

## 🎛️ Customization Guide

### Add New Specialist Agent

```python
# 1. Create specialist function
def create_web_search_agent():
    """Create web search specialist"""
    from langchain_community.tools import DuckDuckGoSearchRun

    search_tool = DuckDuckGoSearchRun()

    return create_retriever_tool(
        search_tool,
        "web_search",
        """Web search specialist. Use for:
        - Current events
        - General knowledge
        - External information

        Returns: Search results from the web"""
    )

# 2. Add to create_multi_agent_graph()
def create_multi_agent_graph():
    # ... existing code ...

    # Create new specialist
    web_agent = create_web_search_agent()

    # Add to agents list
    agents = [genie_agent, rag_agent, web_agent]

    # Add as node
    workflow.add_node("web_search", ToolNode([web_agent]))

    # Update supervisor routing
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            # ... existing routes ...
            "web_search": "web_search",
        }
    )

    # Route back to supervisor
    workflow.add_edge("web_search", "supervisor")
```

### Customize Supervisor Routing Logic

```python
# In create_supervisor_agent()
system_prompt = f"""You are a supervisor agent...

ROUTING RULES:
- For data/SQL queries → SQL_Specialist
- For document/policy questions → document_search
- For current events/external info → web_search  # NEW
- For calculations → calculator_agent            # NEW
- If unsure → HUMAN
- When complete → FINISH

IMPORTANT:
- Call specialists in sequence if needed
- Replan if results insufficient
- Maximum 5 iterations
"""
```

### Add Result Validation/Grading

```python
def create_grader_node():
    """Grade specialist results for relevance"""
    model = AzureChatOpenAI(...)

    def grader_node(state: AgentState):
        messages = state["messages"]

        # Get last specialist result
        last_result = messages[-1].content

        # Grade for relevance
        response = model.invoke([
            SystemMessage(content="Grade if this result answers the question. Respond RELEVANT or NOT_RELEVANT"),
            *messages
        ])

        grade = response.content.strip()

        if grade == "NOT_RELEVANT":
            # Replan
            return {"next_agent": "supervisor", "messages": [AIMessage(content="Result not relevant, trying different approach")]}
        else:
            # Continue
            return {"next_agent": "synthesis", "messages": [AIMessage(content="Result is relevant")]}

    return grader_node

# Add to graph
workflow.add_node("grader", create_grader_node())
workflow.add_edge("SQL_Specialist", "grader")  # Route through grader
workflow.add_conditional_edges("grader", lambda s: s["next_agent"], {...})
```

### Extend State with Custom Fields

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str
    iterations: int
    final_answer: str

    # Custom fields
    confidence: float           # Track confidence scores
    sources: list[str]          # Track all sources used
    intermediate_results: dict  # Store intermediate results
    user_preferences: dict      # Store user preferences
```

---

## 🚀 Usage

### Basic Usage

```python
from src.agent import get_agent

# Get agent
agent = get_agent()

# Query
result = agent.invoke({
    "messages": [HumanMessage(content="What were top 5 products?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

# Extract answer
final_answer = result["final_answer"]
iterations = result["iterations"]
```

### With Conversation Memory

```python
import uuid

# Generate thread ID
thread_id = str(uuid.uuid4())

# First question
result1 = agent.invoke(
    {...},
    config={"configurable": {"thread_id": thread_id}}
)

# Follow-up question (maintains context)
result2 = agent.invoke(
    {"messages": [HumanMessage(content="What about Q3?")], ...},
    config={"configurable": {"thread_id": thread_id}}
)
```

### Streaming Results

```python
# Stream intermediate steps
for chunk in agent.stream(
    {...},
    stream_mode="values"
):
    # Show progress
    if "next_agent" in chunk:
        print(f"Routing to: {chunk['next_agent']}")
```

---

## 📊 Comparison: Before vs After

### BEFORE (Simple Tool Agent)

```python
# Single agent with tools
tools = [genie_tool, rag_tool]
model_with_tools = model.bind_tools(tools)

# Single call
response = model_with_tools.invoke(messages)
```

**Limitations:**
- ❌ No coordination between tools
- ❌ No replanning capability
- ❌ No synthesis of multiple sources
- ❌ No human-in-loop
- ❌ No iteration tracking

### AFTER (Multi-Agent Supervisor)

```python
# Supervisor + Specialists
graph = StateGraph(AgentState)
graph.add_node("supervisor", supervisor)
graph.add_node("SQL_Specialist", sql_specialist)
graph.add_node("document_search", rag_agent)
graph.add_node("synthesis", synthesis)
graph.add_node("human", human)

# Multi-step execution with routing
result = graph.invoke(state)
```

**Capabilities:**
- ✅ Supervisor coordinates specialists
- ✅ Can replan and iterate
- ✅ Synthesizes from multiple sources
- ✅ Human-in-loop when stuck
- ✅ Tracks iterations
- ✅ Conversation memory
- ✅ Extensible architecture

---

## 🎯 Meets Original Requirements

✅ **Deep Agent Orchestrator** - Supervisor coordinates specialists
✅ **Multi-Domain Agents** - SQL, RAG, extensible to add more
✅ **Final Synthesis** - Dedicated synthesis agent
✅ **Replanning** - Supervisor can replan and retry
✅ **Human-in-Loop** - Asks for clarification when stuck
✅ **True Agentic RAG** - Intelligent document retrieval
✅ **Best Practices** - LangGraph patterns, proper state management
✅ **Customizable** - Easy to add specialists and modify routing

---

## 📚 References

- **LangGraph Multi-Agent:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/
- **Supervisor Pattern:** https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale
- **Databricks Genie:** https://docs.databricks.com/generative-ai/agent-framework/multi-agent-genie
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/

---

**Status:** ✅ Complete - Multi-Agent Supervisor Architecture
**Commit:** fad3e08
**Date:** 2026-02-06
