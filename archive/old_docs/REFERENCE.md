# Multi-Agent Orchestrator - API Reference & Examples

**Version:** 2.0.0
**Date:** 2026-02-06
**Pattern:** LangGraph Multi-Agent Supervisor

---

## 📚 Table of Contents

1. [Quick Start](#quick-start)
2. [API Reference](#api-reference)
3. [Usage Examples](#usage-examples)
4. [Configuration Reference](#configuration-reference)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd Langgraph-MultiAgent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Validate setup
python validate_setup.py

# Run the system
python src/main.py
```

### Basic Usage

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent

# Initialize agent
agent = get_agent()

# Query
result = agent.invoke({
    "messages": [HumanMessage(content="What were top 5 products by revenue?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

# Extract answer
print(result["final_answer"])
```

---

## API Reference

### AgentState

State object passed between agents in the graph.

```python
class AgentState(TypedDict):
    """State for multi-agent system"""
    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str           # Which agent to call next
    iterations: int           # Iteration counter (prevents loops)
    final_answer: str         # Final synthesized answer
```

**Fields:**
- `messages` (list[BaseMessage]): Conversation history with automatic accumulation
- `next_agent` (str): Name of next agent to route to ("FINISH", "HUMAN", "SQL_Specialist", "document_search")
- `iterations` (int): Number of iterations executed (max 5 before asking human)
- `final_answer` (str): Synthesized final answer from synthesis agent

---

### get_agent()

Get or create the singleton agent graph.

```python
def get_agent() -> CompiledGraph
```

**Returns:** Compiled LangGraph StateGraph

**Example:**
```python
from src.agent import get_agent

agent = get_agent()
```

**Note:** This uses singleton pattern - first call initializes, subsequent calls return cached instance.

---

### Agent Invocation

#### Basic Invocation

```python
result = agent.invoke(state: AgentState) -> AgentState
```

**Parameters:**
- `state` (AgentState): Initial state with user question

**Returns:** AgentState with final answer

**Example:**
```python
from langchain_core.messages import HumanMessage

result = agent.invoke({
    "messages": [HumanMessage(content="What were our sales last quarter?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

print(result["final_answer"])
# Output: Based on the sales data, Q4 revenue was $2.3M...
```

---

#### Invocation with Memory

```python
result = agent.invoke(
    state: AgentState,
    config: dict = {"configurable": {"thread_id": str}}
) -> AgentState
```

**Parameters:**
- `state` (AgentState): Initial state
- `config` (dict): Configuration with thread_id for conversation memory

**Returns:** AgentState with context from previous messages

**Example:**
```python
import uuid

thread_id = str(uuid.uuid4())

# First question
result1 = agent.invoke(
    {
        "messages": [HumanMessage(content="What were sales in Q4?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)

# Follow-up question (remembers Q4 context)
result2 = agent.invoke(
    {
        "messages": [HumanMessage(content="What about Q3?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)
```

---

#### Streaming Results

```python
for chunk in agent.stream(
    state: AgentState,
    stream_mode: str = "values"
) -> Iterator[AgentState]
```

**Parameters:**
- `state` (AgentState): Initial state
- `stream_mode` (str): "values", "updates", or "debug"

**Yields:** AgentState updates

**Example:**
```python
for chunk in agent.stream(
    {
        "messages": [HumanMessage(content="Analyze customer data")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    stream_mode="values"
):
    if "next_agent" in chunk:
        print(f"→ Routing to: {chunk['next_agent']}")

    if "final_answer" in chunk and chunk["final_answer"]:
        print(f"✓ Final answer: {chunk['final_answer']}")
```

---

### Specialist Agents

#### GenieAgent (SQL Specialist)

```python
def create_genie_agent() -> GenieAgent
```

**Returns:** GenieAgent tool for SQL queries

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

**Example:**
```python
from src.agent import create_genie_agent

genie = create_genie_agent()

# Called automatically by supervisor when routing to "SQL_Specialist"
```

---

#### RAG Agent (Document Search)

```python
def create_rag_agent() -> Tool
```

**Returns:** Retriever tool for document search

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

**Example:**
```python
from src.agent import create_rag_agent

rag = create_rag_agent()

# Called automatically by supervisor when routing to "document_search"
```

---

### Configuration

#### Configuration Classes

```python
from src.core.config import config

# Access configuration
print(config.azure_openai.endpoint)
print(config.databricks.host)
print(config.llm.temperature)
```

**Available Configs:**
- `config.azure_openai` - Azure OpenAI settings
- `config.databricks` - Databricks settings
- `config.llm` - LLM parameters
- `config.embedding` - Embedding settings
- `config.rag` - RAG settings

**Example:**
```python
from src.core.config import config

# Azure OpenAI
endpoint = config.azure_openai.endpoint
api_key = config.azure_openai.api_key
gpt4o_deployment = config.azure_openai.gpt4o_deployment

# Databricks
host = config.databricks.host
token = config.databricks.token
genie_space_id = config.databricks.genie_space_id
tables = config.databricks.unity_tables  # List[str]

# LLM
temperature = config.llm.temperature  # 0.7
max_tokens = config.llm.max_tokens    # 4096

# Embedding
chunk_size = config.embedding.chunk_size      # 1000
chunk_overlap = config.embedding.chunk_overlap  # 200
```

---

## Usage Examples

### Example 1: Simple SQL Query

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent

agent = get_agent()

result = agent.invoke({
    "messages": [HumanMessage(content="What were our top 5 products by revenue?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

print(result["final_answer"])
```

**Expected Flow:**
1. Supervisor → SQL_Specialist
2. SQL_Specialist queries Genie → returns results
3. Supervisor → Synthesis
4. Synthesis → Final answer

**Output:**
```
Based on the sales data, here are the top 5 products by revenue:

1. Product A - $1.2M
2. Product B - $980K
3. Product C - $850K
4. Product D - $720K
5. Product E - $680K

Sources: Unity Catalog (SQL), sales_data table
```

---

### Example 2: Document Search

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent

agent = get_agent()

result = agent.invoke({
    "messages": [HumanMessage(content="What is our company's return policy?")],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

print(result["final_answer"])
```

**Expected Flow:**
1. Supervisor → document_search
2. document_search retrieves policy document
3. Supervisor → Synthesis
4. Synthesis → Final answer with citations

---

### Example 3: Multi-Agent Coordination

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent

agent = get_agent()

result = agent.invoke({
    "messages": [HumanMessage(
        content="Compare our Q4 sales against company policy targets"
    )],
    "next_agent": "",
    "iterations": 0,
    "final_answer": ""
})

print(result["final_answer"])
```

**Expected Flow:**
1. Supervisor → SQL_Specialist (get Q4 sales data)
2. Supervisor → document_search (get policy targets)
3. Supervisor → Synthesis (combine both sources)
4. Synthesis → Comprehensive answer

---

### Example 4: Conversation with Memory

```python
import uuid
from langchain_core.messages import HumanMessage
from src.agent import get_agent

agent = get_agent()
thread_id = str(uuid.uuid4())

# Question 1
result1 = agent.invoke(
    {
        "messages": [HumanMessage(content="What were sales in Q4 2025?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)
print("Q1:", result1["final_answer"])

# Question 2 (remembers Q4 context)
result2 = agent.invoke(
    {
        "messages": [HumanMessage(content="How does that compare to Q3?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)
print("Q2:", result2["final_answer"])

# Question 3 (remembers both previous questions)
result3 = agent.invoke(
    {
        "messages": [HumanMessage(content="What was the growth rate?")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    config={"configurable": {"thread_id": thread_id}}
)
print("Q3:", result3["final_answer"])
```

---

### Example 5: Streaming Progress

```python
from langchain_core.messages import HumanMessage
from src.agent import get_agent

agent = get_agent()

print("Processing query...")

for chunk in agent.stream(
    {
        "messages": [HumanMessage(content="Analyze customer demographics")],
        "next_agent": "",
        "iterations": 0,
        "final_answer": ""
    },
    stream_mode="values"
):
    # Show routing decisions
    if "next_agent" in chunk and chunk["next_agent"]:
        print(f"→ Routing to: {chunk['next_agent']}")

    # Show iterations
    if "iterations" in chunk:
        print(f"  Iteration: {chunk['iterations']}")

    # Show final answer
    if "final_answer" in chunk and chunk["final_answer"]:
        print(f"\n✓ Answer:\n{chunk['final_answer']}")
```

---

## Configuration Reference

### Environment Variables

```bash
# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Databricks (Required)
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=your-databricks-token
DATABRICKS_SQL_WAREHOUSE_ID=your-warehouse-id
GENIE_SPACE_ID=your-genie-space-id
UNITY_CATALOG_TABLES=sales_data,customer_data,product_data

# LLM Settings (Optional)
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# Embedding Settings (Optional)
EMBEDDING_CHUNK_SIZE=1000
EMBEDDING_CHUNK_OVERLAP=200

# RAG Settings (Optional)
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7

# Logging (Optional)
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### .env.example

See `.env.example` file in repository for complete template.

---

## Common Patterns

### Pattern 1: Add Custom Specialist Agent

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

    # Update routing
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

---

### Pattern 2: Custom State Fields

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
```

---

### Pattern 3: Result Validation/Grading

```python
def create_grader_node():
    """Grade specialist results for relevance"""
    model = AzureChatOpenAI(...)

    def grader_node(state: AgentState):
        messages = state["messages"]
        last_result = messages[-1].content

        # Grade for relevance
        response = model.invoke([
            SystemMessage(content="Grade if this result answers the question. Respond RELEVANT or NOT_RELEVANT"),
            *messages
        ])

        grade = response.content.strip()

        if grade == "NOT_RELEVANT":
            return {"next_agent": "supervisor", "messages": [AIMessage(content="Result not relevant, replanning")]}
        else:
            return {"next_agent": "synthesis", "messages": [AIMessage(content="Result is relevant")]}

    return grader_node

# Add to graph
workflow.add_node("grader", create_grader_node())
workflow.add_edge("SQL_Specialist", "grader")
workflow.add_conditional_edges("grader", lambda s: s["next_agent"], {...})
```

---

### Pattern 4: Custom Supervisor Routing

```python
# Update system prompt in create_supervisor_agent()
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

---

## Troubleshooting

### Common Issues

**1. Import Error: GenieAgent**

```
Error: cannot import name 'GenieAgent' from 'databricks_langchain.genie'
```

**Solution:** Ensure `databricks-langchain>=0.14.0` is installed:
```bash
pip install databricks-langchain>=0.14.0
```

---

**2. Databricks Authentication Failed**

```
Error: Failed to initialize Databricks client
```

**Solution:** Check environment variables:
```bash
echo $DATABRICKS_HOST
echo $DATABRICKS_TOKEN
```

Ensure `.env` file has correct values.

---

**3. Genie Query Timeout**

```
Error: Genie query timeout
```

**Solution:**
- Check Genie Space ID is correct
- Ensure SQL Warehouse is running
- Verify Unity Catalog tables exist

---

**4. No Documents Found for RAG**

```
Warning: No documents found - RAG agent not available
```

**Solution:** Add documents to `data/documents/` directory:
```bash
mkdir -p data/documents
cp your-docs/*.pdf data/documents/
```

Supported formats: PDF, DOCX, TXT, CSV, XLSX, PPTX

---

**5. Configuration Parsing Error**

```
Error: json.decoder.JSONDecodeError
```

**Solution:** Check `.env` file format. Values should be plain text, not JSON:
```bash
# Correct
UNITY_CATALOG_TABLES=sales_data,customer_data,product_data

# Wrong
UNITY_CATALOG_TABLES=["sales_data","customer_data"]
```

---

**6. Memory/Checkpointing Issues**

```
Error: Checkpointer error
```

**Solution:** Memory is stored in-memory. For production, use persistent checkpointer:
```python
from langgraph.checkpoint.postgres import PostgresSaver

# Instead of MemorySaver()
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
graph = workflow.compile(checkpointer=checkpointer)
```

---

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from src.agent import get_agent
agent = get_agent()
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
python src/main.py
```

---

## Performance Tips

### 1. Reduce Latency

- Use conversation memory to avoid reprocessing context
- Keep document corpus small and focused
- Use faster embedding model if needed

### 2. Improve Accuracy

- Provide clear, specific questions
- Add more context in follow-up questions
- Ensure Unity Catalog tables have good metadata

### 3. Handle Errors Gracefully

- System has built-in retry logic
- Supervisor replans on failures
- Human-in-loop after 5 iterations

---

## API Limits

### Azure OpenAI

- Default rate limits apply
- GPT-4o: ~10K tokens/min
- Embeddings: ~350K tokens/min

### Databricks Genie

- Query timeout: 30 seconds
- Concurrent requests: Limited by workspace tier
- Result size: Up to 1000 rows

---

## Next Steps

1. **Read CLAUDE.md** for architecture and concepts
2. **Read SKILLS.md** for system capabilities
3. **Run validate_setup.py** to verify configuration
4. **Try examples above** to get familiar with the API
5. **Customize** by adding new specialist agents

---

**Version:** 2.0.0
**Date:** 2026-02-06
**Status:** ✅ Production-Ready
