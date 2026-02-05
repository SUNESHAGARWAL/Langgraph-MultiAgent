<!-- This is the documentation for this codebase. Read this carefully before making changes. Claude will use this file. -->

# Multi-Agent Orchestrator System - Architecture & Implementation Guide

**Version:** 1.0.0
**Last Updated:** 2026-02-05
**Tech Stack:** LangGraph v1.0.7, Databricks Genie, Azure OpenAI GPT-4o, MLflow, FAISS, Redis

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Data Flow](#data-flow)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Development](#development)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## Overview

### Purpose

This system acts as an intelligent orchestrator for multi-agent workflows, specifically designed to handle complex data queries through Databricks Genie while incorporating:
- **Smart SQL Caching** with semantic similarity
- **Table Understanding** via EDA and metadata
- **Document RAG** for context enrichment
- **Human-in-the-Loop** for clarifications
- **Feedback Loops** for error recovery and replanning

### Key Features

✅ **Multi-Agent Orchestration** - Coordinates Genie, RAG, and Table Understanding agents
✅ **Semantic Caching** - Reuses similar queries via vector similarity (Redis/FAISS)
✅ **Intelligent Planning** - Creates execution plans and replans on failures
✅ **Agentic RAG** - Auto-processes documents (PDF, DOCX, CSV, etc.) with file monitoring
✅ **Table Discovery** - EDA-based understanding of Unity Catalog tables
✅ **Production-Grade** - MLflow tracking, OpenTelemetry tracing, comprehensive logging
✅ **Extensible** - Easy to add new agents and data sources

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   Orchestrator Agent       │
        │   (Planning & Routing)     │
        └────────────┬───────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
        ▼            ▼            ▼            ▼
   ┌────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐
   │ Genie  │  │  Table  │  │   RAG   │  │  Human   │
   │ Agent  │  │  Agent  │  │  Agent  │  │   Loop   │
   └───┬────┘  └────┬────┘  └────┬────┘  └────┬─────┘
       │            │            │            │
       └────────────┴────────────┴────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   Synthesis Agent          │
        │   (Final Answer)           │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   Smart Cache              │
        │   (Store for reuse)        │
        └────────────────────────────┘

[Feedback Loop: Orchestrator replans if any step fails]
```

### System Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Orchestrator Agent** | Planning, routing, error handling | Azure OpenAI GPT-4o |
| **Genie Agent** | SQL query execution | Databricks Genie API |
| **Table Understanding Agent** | EDA and metadata extraction | Databricks SQL, FAISS |
| **RAG Agent** | Document processing and retrieval | FAISS, Watchdog |
| **Synthesis Agent** | Final answer generation | Azure OpenAI GPT-4o |
| **Human Loop** | Clarifications and confirmations | CLI/API callbacks |
| **Smart Cache** | Semantic query caching | Redis/FAISS |
| **Vector Store** | Embeddings storage | FAISS |
| **MLflow Tracker** | Experiment tracking | Databricks MLflow |
| **Blob Storage** | Data persistence | Azure Blob Storage |

---

## Components

### 1. Orchestrator Agent (`src/agents/orchestrator.py`)

**Responsibility:** Brain of the system - plans, routes, and recovers from failures.

**Key Methods:**
- `orchestrate(question, conversation_history, context)` - Main entry point
- `_create_plan(question, ...)` - Creates execution plan using GPT-4o
- `_execute_plan(plan, ...)` - Executes plan step-by-step
- `_replan(previous_plan, execution_log, question)` - Replans on failure

**Planning Algorithm:**
1. Analyze user question
2. Identify required agents (Genie, Table, RAG)
3. Create step-by-step plan with dependencies
4. Execute steps sequentially
5. On failure → check if human input needed OR replan
6. Iterate until success or max iterations

**Example Plan:**
```json
{
  "analysis": "User wants top 5 products by revenue",
  "confidence": 0.9,
  "steps": [
    {
      "step": 1,
      "agent": "TABLE_UNDERSTANDING",
      "action": "Find tables related to products and revenue",
      "depends_on": []
    },
    {
      "step": 2,
      "agent": "GENIE",
      "action": "Query top 5 products by revenue from identified table",
      "depends_on": [1]
    }
  ]
}
```

### 2. Genie Agent (`src/agents/genie_agent.py`)

**Responsibility:** Execute natural language SQL queries via Databricks Genie.

**Key Features:**
- Semantic caching with vector similarity
- Exponential backoff retry logic
- Polling-based result retrieval
- Result formatting and parsing

**Flow:**
1. Check cache for similar queries (similarity > 0.85)
2. If miss → create Genie conversation
3. Poll for completion (timeout: 30s)
4. Parse results (SQL + data)
5. Cache the result
6. Return formatted response

**Cache Key:** Natural language question
**Cache Value:** SQL query + results + metadata

### 3. Table Understanding Agent (`src/agents/table_understanding.py`)

**Responsibility:** Understand Unity Catalog tables via EDA.

**Key Features:**
- Extracts table schemas (DESCRIBE TABLE EXTENDED)
- Computes statistics (row counts, distinct counts)
- Samples data for context
- Stores metadata in vector store + blob storage
- Enables semantic table search

**Initialization:**
```python
table_agent.analyze_all_tables(force_refresh=False)
```

**Search Example:**
```python
tables = table_agent.search_tables(
    query="customer purchase data",
    top_k=3
)
# Returns: [{"table_name": "sales_data", "similarity": 0.92, ...}, ...]
```

### 4. RAG Agent (`src/agents/rag_agent.py`)

**Responsibility:** Process documents and provide context for queries.

**Key Features:**
- Auto-monitors directory with Watchdog
- Supports: PDF, DOCX, CSV, TXT, PPTX, XLSX
- Chunks documents (1000 chars, 200 overlap)
- Embeds and stores in FAISS
- Retrieves relevant context via similarity search

**Auto-Processing:**
1. File dropped in `RAG_WATCH_PATH`
2. Watchdog detects event
3. Parse document
4. Chunk text
5. Generate embeddings
6. Store in vector store
7. Save metadata to blob storage

**Retrieval:**
```python
contexts = rag_agent.retrieve_context(
    query="customer churn analysis",
    top_k=5,
    similarity_threshold=0.7
)
```

### 5. Synthesis Agent (`src/agents/synthesis_agent.py`)

**Responsibility:** Combine results from multiple agents into coherent answer.

**Process:**
1. Extract Genie results (SQL + data)
2. Extract RAG context (document chunks)
3. Extract table metadata
4. Format all information
5. Use GPT-4o to synthesize final answer
6. Add source attribution

**Example Output:**
```
Based on the sales data, here are the top 5 products by revenue:

1. Product A - $1.2M
2. Product B - $980K
3. Product C - $850K
4. Product D - $720K
5. Product E - $680K

Sources: Unity Catalog (SQL), sales_data table
```

### 6. Human-in-Loop (`src/agents/human_loop.py`)

**Responsibility:** Handle clarifications and confirmations.

**Key Methods:**
- `ask_clarification(question, suggestions)` - Ask for more info
- `ask_confirmation(action, details)` - Confirm before action
- `ask_choice(question, choices)` - Multiple choice
- `notify(message, level)` - Display notifications

**Trigger Conditions:**
- Orchestrator confidence < 0.7
- Ambiguous query
- Multiple valid interpretations
- Missing required information

### 7. Smart Cache (`src/services/caching.py`)

**Responsibility:** Semantic caching with vector similarity.

**Implementation:**
- **Primary:** Redis with RedisVL (if available)
- **Fallback:** FAISS-based file storage

**Similarity Matching:**
```python
# Set cache
cache.set(
    key="What were sales last quarter?",
    value={"result": ...},
    ttl=3600,
    tags=["genie_query"]
)

# Search similar
results = cache.search_similar(
    query="Show me last quarter's revenue",
    similarity_threshold=0.85,
    top_k=1
)
# Returns hit if cosine similarity > 0.85
```

**TTL & Eviction:**
- Default TTL: 3600s (1 hour)
- Configurable per entry
- Auto-cleanup on expiry

### 8. Vector Store (`src/services/vector_store.py`)

**Responsibility:** FAISS-based vector storage for multiple use cases.

**Stores:**
- `sql_cache` - Cached SQL queries
- `table_metadata` - Table/column information
- `rag_documents` - Document chunks

**Operations:**
- `add_documents(texts, metadatas, ids)` - Add vectors
- `similarity_search(query, k, score_threshold)` - Search
- `get_by_id(doc_id)` - Retrieve by ID
- `save()` - Persist to disk

### 9. MLflow Tracker (`src/services/mlflow_tracker.py`)

**Responsibility:** Experiment tracking and observability.

**Tracked Metrics:**
- Query latency
- Cache hit rate
- Iterations to success
- Agent execution times
- Error rates

**Usage:**
```python
with tracker.start_run(run_name="query_123"):
    tracker.log_params({"question": "..."})
    # ... process ...
    tracker.log_metrics({"latency_seconds": 2.5})
    tracker.log_agent_interaction(...)
```

**Dashboard:** View in Databricks MLflow UI

---

## Data Flow

### Complete Query Flow

```
1. User asks: "What were our top 5 products by revenue last quarter?"

2. Orchestrator receives question
   ├─ Creates initial plan
   ├─ Steps: [Table Search → Genie Query → Synthesis]
   └─ Confidence: 0.9

3. Execute Step 1: Table Understanding
   ├─ Search for "products revenue" in vector store
   ├─ Found: sales_data (similarity: 0.95)
   └─ Returns: table metadata

4. Execute Step 2: Genie Query
   ├─ Check cache for similar query
   ├─ Cache MISS
   ├─ Call Genie API with "top 5 products by revenue from sales_data"
   ├─ Poll for results (3 attempts, 6s)
   ├─ Receive: SQL + 5 rows of data
   └─ Cache the result

5. Synthesis Agent
   ├─ Combines table metadata + Genie results
   ├─ Formats as human-readable answer
   └─ Adds source attribution

6. Return to user
   ├─ Answer: "Based on sales_data, top 5 products are..."
   ├─ Latency: 8.2s
   └─ Sources: [Unity Catalog (SQL)]

7. Update conversation history
   └─ Store in session for context
```

### Caching Flow

```
Query 1: "What were sales last quarter?"
├─ Cache MISS
├─ Execute Genie
├─ Store result with embedding
└─ Latency: 8s

Query 2: "Show me revenue from previous quarter"
├─ Check cache
├─ Compute similarity with Query 1
├─ Similarity: 0.89 (> 0.85 threshold)
├─ Cache HIT
└─ Latency: 0.3s  [27x faster!]
```

### Feedback Loop Flow

```
Iteration 1:
├─ Plan: [Genie Query]
├─ Execute: Genie query fails (table not found)
└─ Result: FAILURE

Iteration 2:
├─ Replan: [Table Understanding → Genie Query]
├─ Execute: Find correct table → Query succeeds
└─ Result: SUCCESS

Total iterations: 2
```

---

## Configuration

### Environment Variables

All configuration in `.env` file. See `.env.example` for template.

**Critical Variables:**

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Databricks
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=your-token
GENIE_SPACE_ID=your-genie-space-id
UNITY_CATALOG_TABLES=sales_data,customer_data,product_data

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# RAG
RAG_WATCH_PATH=/path/to/documents

# Caching
REDIS_ENABLED=false  # Set to true if Redis available
CACHE_SIMILARITY_THRESHOLD=0.85

# MLflow
MLFLOW_EXPERIMENT_NAME=/Users/you@company.com/multi-agent
```

### Configuration Classes

See `src/core/config.py` for all configuration options.

**Accessing Config:**
```python
from src.core.config import config

# Access nested configs
endpoint = config.azure_openai.endpoint
tables = config.databricks.unity_tables
cache_ttl = config.cache.ttl_seconds
```

---

## Usage

### CLI Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your credentials

# Run CLI
python src/main.py
```

**CLI Example:**
```
╔═══════════════════════════════════════════════════════════╗
║   Multi-Agent Orchestrator v1.0.0                         ║
║   Environment: development                                ║
╚═══════════════════════════════════════════════════════════╝

📊 Analyzing Unity Catalog tables...
✓ Analyzed 3 tables

💬 Ready for questions! (type 'exit' to quit)

🤔 You: What were our top 5 products by revenue last quarter?

🤖 Processing...

✨ Answer:
Based on the sales data, here are the top 5 products by revenue:

1. Product A - $1.2M
2. Product B - $980K
3. Product C - $850K
4. Product D - $720K
5. Product E - $680K

📚 Sources: Unity Catalog (SQL)
⏱️ Latency: 8.24s

🤔 You: exit
👋 Goodbye!
```

### Python API Usage

```python
from src.main import MultiAgentOrchestrator

# Initialize
orchestrator = MultiAgentOrchestrator(auto_start_rag=True)

# Analyze tables (one-time setup)
orchestrator.analyze_tables()

# Query
result = orchestrator.query(
    question="What were our top 5 products by revenue last quarter?",
    session_id="user-123"
)

if result["success"]:
    print(f"Answer: {result['answer']}")
    print(f"Sources: {result['sources']}")
    print(f"Latency: {result['latency']:.2f}s")
else:
    print(f"Error: {result['error']}")

# Handle clarification
if result.get("needs_clarification"):
    clarification = input(result["clarification_question"])

    result = orchestrator.provide_clarification(
        session_id="user-123",
        clarification=clarification
    )

# Cleanup
orchestrator.cleanup()
```

### Advanced Usage

**Custom Input Callback:**
```python
def my_input_callback(prompt):
    # Custom UI for getting user input
    return custom_ui.get_input(prompt)

from src.agents.human_loop import get_human_loop_agent
human_loop = get_human_loop_agent(input_callback=my_input_callback)
```

**Direct Agent Access:**
```python
from src.agents.genie_agent import get_genie_agent

genie = get_genie_agent()
result = genie.query("Show sales data")
```

---

## Development

### Project Structure

```
Langgraph-MultiAgent/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── agents/                    # All agent implementations
│   │   ├── orchestrator.py        # Main orchestrator
│   │   ├── genie_agent.py         # Databricks Genie
│   │   ├── table_understanding.py # EDA agent
│   │   ├── rag_agent.py           # RAG system
│   │   ├── synthesis_agent.py     # Answer synthesis
│   │   └── human_loop.py          # Human interaction
│   ├── core/                      # Core components
│   │   ├── config.py              # Configuration management
│   │   └── state.py               # State definitions
│   ├── services/                  # Supporting services
│   │   ├── caching.py             # Smart cache
│   │   ├── vector_store.py        # FAISS operations
│   │   ├── storage.py             # Azure Blob Storage
│   │   ├── mlflow_tracker.py      # MLflow tracking
│   │   └── file_monitor.py        # Watchdog file monitoring
│   └── utils/                     # Utilities
│       ├── logging.py             # Structured logging
│       ├── embeddings.py          # Embedding service
│       └── parsers.py             # Document parsers
├── tests/                         # Test suite
├── configs/                       # Configuration files
├── requirements.txt               # Dependencies
├── .env.example                   # Environment template
├── CLAUDE.md                      # This file
├── SKILLS.md                      # Agent capabilities
├── PROGRESS.md                    # Development progress
└── README.md                      # Quick start guide
```

### Adding a New Agent

1. Create agent file in `src/agents/`:

```python
# src/agents/my_new_agent.py

from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)

class MyNewAgent:
    def __init__(self):
        logger.info("Initialized MyNewAgent")

    @trace_function("my_action")
    @track_agent("my_new_agent")
    def process(self, input_data):
        # Your logic here
        return {"result": "..."}

_my_agent = None

def get_my_agent():
    global _my_agent
    if _my_agent is None:
        _my_agent = MyNewAgent()
    return _my_agent
```

2. Register in orchestrator (`src/agents/orchestrator.py`):

```python
# Add to __init__
self.my_agent = get_my_agent()

# Add to agent execution
elif agent_name == "MY_NEW_AGENT":
    result = self.my_agent.process(action)
```

3. Update planning prompt to include new agent

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_orchestrator.py

# With coverage
pytest --cov=src tests/
```

### Logging

**View Logs:**
```bash
# JSON format (production)
tail -f logs/app.log | jq .

# Human-readable (development)
LOG_FORMAT=text python src/main.py
```

**Log Levels:**
- `DEBUG`: Detailed information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Tracing

**OpenTelemetry:**
```bash
# View traces in Jaeger
docker run -d -p 16686:16686 jaegertracing/all-in-one:latest

# Set endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**LangSmith:**
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key
```

---

## Troubleshooting

### Common Issues

**1. Databricks Connection Failed**
```
Error: Failed to initialize Databricks client
```
**Solution:** Check `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in `.env`

**2. Genie Query Timeout**
```
Error: Genie query timeout after 30 seconds
```
**Solution:** Increase `GENIE_TIMEOUT` or check Genie Space availability

**3. Cache Not Working**
```
Warning: Redis not available, falling back to FAISS
```
**Solution:** This is expected if Redis not installed. System uses FAISS fallback.

**4. File Monitoring Not Starting**
```
Error: Failed to start file monitor
```
**Solution:** Check `RAG_WATCH_PATH` exists and is accessible

**5. MLflow Experiment Not Found**
```
Error: Experiment not found
```
**Solution:** Check `MLFLOW_EXPERIMENT_NAME` format: `/Users/your-email/experiment-name`

### Debug Mode

```bash
# Enable verbose logging
LOG_LEVEL=DEBUG python src/main.py

# Enable tracing
ENABLE_TRACING=true python src/main.py
```

### Performance Tuning

**Improve Cache Hit Rate:**
```bash
CACHE_SIMILARITY_THRESHOLD=0.80  # Lower = more hits (but less accurate)
```

**Reduce Latency:**
```bash
GENIE_TIMEOUT=20  # Lower timeout
ASYNC_WORKERS=8   # More parallel workers
```

**Reduce Costs:**
```bash
AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=gpt-4o-mini  # Use cheaper model
CACHE_TTL_SECONDS=7200  # Cache longer
```

---

## API Reference

### MultiAgentOrchestrator

```python
class MultiAgentOrchestrator:
    def __init__(self, auto_start_rag: bool = True)

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]

    def provide_clarification(
        self,
        session_id: str,
        clarification: str,
    ) -> Dict[str, Any]

    def analyze_tables(self, force_refresh: bool = False) -> Dict[str, Any]

    def get_stats(self) -> Dict[str, Any]

    def cleanup(self)
```

### Response Format

```python
{
    "success": True,
    "answer": "The top 5 products by revenue are...",
    "sources": ["Unity Catalog (SQL)"],
    "plan": {...},
    "execution_log": [...],
    "iterations": 1,
    "latency": 8.24,
    "session_id": "uuid",
    "request_id": "uuid"
}
```

---

## References

- **LangGraph**: https://docs.langchain.com/oss/python/langgraph/
- **Databricks Genie**: https://docs.databricks.com/en/generative-ai/agent-framework/multi-agent-genie
- **Azure OpenAI**: https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **MLflow**: https://docs.databricks.com/en/mlflow/
- **FAISS**: https://docs.langchain.com/oss/python/integrations/vectorstores/faiss

---

## License

Proprietary - All Rights Reserved

## Support

For issues or questions, please refer to PROGRESS.md for current development status.

---

**Last Updated:** 2026-02-05
**Version:** 1.0.0
**Status:** Production-Ready
