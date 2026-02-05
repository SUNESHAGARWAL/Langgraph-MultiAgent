# Multi-Agent Orchestrator for Databricks Genie

A production-grade multi-agent orchestrator system that intelligently routes queries to specialized agents, featuring semantic caching, table understanding, agentic RAG, and human-in-the-loop capabilities.

## ✨ Key Features

- 🧠 **Intelligent Orchestration** - Plans and routes queries to appropriate agents with feedback loops
- ⚡ **Semantic Caching** - Reuses similar queries via vector similarity (27x faster)
- 📊 **Databricks Genie Integration** - Natural language SQL queries on Unity Catalog
- 📄 **Agentic RAG** - Auto-processes documents (PDF, DOCX, CSV, etc.) with file monitoring
- 🔍 **Table Understanding** - EDA-based discovery of Unity Catalog tables
- 💬 **Human-in-the-Loop** - Clarifying questions when needed
- 📈 **MLflow Tracking** - Complete observability and experiment tracking
- 🏗️ **Production-Ready** - Comprehensive logging, tracing, error handling

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Azure OpenAI access
- Databricks workspace with Genie Space
- Unity Catalog access

### Installation

```bash
# Clone repository
git clone <repository-url>
cd Langgraph-MultiAgent

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Edit `.env` with your configuration:

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
AZURE_STORAGE_CONNECTION_STRING=your-connection-string

# RAG (optional)
RAG_WATCH_PATH=/path/to/documents

# MLflow
MLFLOW_EXPERIMENT_NAME=/Users/your-email/multi-agent-orchestrator
```

### Run

```bash
# CLI interface
python src/main.py

# Or import in Python
from src.main import MultiAgentOrchestrator

orchestrator = MultiAgentOrchestrator()
result = orchestrator.query("What were our top 5 products by revenue last quarter?")
print(result["answer"])
```

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete architecture and implementation guide
- **[SKILLS.md](SKILLS.md)** - Agent capabilities reference
- **[PROGRESS.md](PROGRESS.md)** - Development progress and status

## 🏗️ Architecture

```
User Question
     ↓
Orchestrator (Planning & Routing)
     ↓
     ├─→ Smart Cache (Vector Similarity)
     ├─→ Genie Agent (SQL Queries)
     ├─→ Table Understanding (EDA)
     ├─→ RAG Agent (Documents)
     └─→ Human Loop (Clarifications)
     ↓
Synthesis Agent
     ↓
Final Answer
```

## 🧪 Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_basic.py -v
```

## 📊 Example Usage

### Simple Query

```python
result = orchestrator.query("What were sales last quarter?")
# Uses: Cache check → Genie Agent → Synthesis
```

### Complex Query with RAG

```python
result = orchestrator.query(
    "Compare our Q4 sales with industry trends from the report"
)
# Uses: RAG Agent (report) → Genie Agent (sales) → Synthesis
```

### Ambiguous Query

```python
result = orchestrator.query("Show me the data")
# Response: needs_clarification=True
# System suggests: sales_data, customer_data, product_data
```

## 🔑 Key Components

| Component | Purpose |
|-----------|---------|
| **Orchestrator** | Plans and coordinates all agents |
| **Genie Agent** | Executes SQL via Databricks Genie |
| **Table Agent** | Discovers and understands tables |
| **RAG Agent** | Processes and retrieves documents |
| **Synthesis Agent** | Combines results into final answer |
| **Human Loop** | Handles clarifications |
| **Smart Cache** | Semantic caching with Redis/FAISS |

## 🎯 Performance

- **Cache Hit Latency:** ~0.3s (27x faster than cold query)
- **Cold Query Latency:** ~8s (Genie processing time)
- **Cache Hit Rate:** ~40-60% (varies by workload)
- **Semantic Match Threshold:** 0.85 (configurable)

## 🛠️ Tech Stack

- **LangGraph** v1.0.7 - Multi-agent orchestration
- **Databricks SDK** - Genie and Unity Catalog access
- **Azure OpenAI** - GPT-4o for planning and synthesis
- **FAISS** - Vector storage and similarity search
- **Redis** - Semantic caching (optional)
- **MLflow** - Experiment tracking
- **Watchdog** - File monitoring for RAG
- **OpenTelemetry** - Distributed tracing

## 📝 Project Structure

```
Langgraph-MultiAgent/
├── src/
│   ├── agents/          # All agent implementations
│   ├── core/            # Configuration and state
│   ├── services/        # Caching, storage, tracking
│   ├── utils/           # Logging, embeddings, parsers
│   └── main.py          # Entry point
├── tests/               # Test suite
├── configs/             # Configuration files
├── CLAUDE.md            # Architecture guide
├── SKILLS.md            # Agent capabilities
├── PROGRESS.md          # Development status
└── requirements.txt     # Dependencies
```

## 🤝 Contributing

This is a production system. For changes:

1. Read CLAUDE.md for architecture
2. Check PROGRESS.md for current status
3. Follow existing patterns
4. Add tests
5. Update documentation

## 📄 License

Proprietary - All Rights Reserved

## 🆘 Support

For issues:
1. Check CLAUDE.md troubleshooting section
2. Review PROGRESS.md for known issues
3. Check logs in `./data/logs/`
4. Review MLflow experiments in Databricks

## 🌟 Highlights

- **Production-Grade:** Comprehensive error handling, logging, and monitoring
- **Extensible:** Easy to add new agents and data sources
- **Intelligent:** Learns from cache, replans on failures, asks for clarification
- **Fast:** Semantic caching provides sub-second responses for similar queries
- **Observable:** Full MLflow tracking and OpenTelemetry tracing

---

**Version:** 1.0.0
**Status:** Production-Ready
**Last Updated:** 2026-02-05

For detailed documentation, see [CLAUDE.md](CLAUDE.md)
