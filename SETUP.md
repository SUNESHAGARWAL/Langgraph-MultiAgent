# Multi-Agent Orchestrator System - Setup Guide

**Last Updated:** 2026-02-06
**Version:** 1.0.0
**Status:** Production-Ready

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Azure OpenAI Setup](#azure-openai-setup)
4. [Databricks Setup](#databricks-setup)
5. [Azure Blob Storage Setup](#azure-blob-storage-setup)
6. [Configuration](#configuration)
7. [Validation](#validation)
8. [First Run](#first-run)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services

You need access to the following cloud services:

- **Azure OpenAI Service** (GPT-4o and text-embedding-ada-002)
- **Databricks Workspace** with:
  - SQL Warehouse (Serverless or Pro)
  - Unity Catalog enabled
  - Genie Space created
- **Azure Blob Storage Account**

### System Requirements

- **Python:** 3.11 or higher
- **Memory:** Minimum 4GB RAM
- **Disk Space:** 2GB for dependencies and data
- **OS:** Windows, Linux, or macOS

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/Langgraph-MultiAgent.git
cd Langgraph-MultiAgent
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# This installs:
# - LangChain and LangGraph for agent orchestration
# - Databricks SDK for Genie and SQL execution
# - Azure SDKs for OpenAI and Blob Storage
# - FAISS for vector search
# - MLflow for tracking
# - And more...
```

---

## Azure OpenAI Setup

### Step 1: Get Azure OpenAI Endpoint and Key

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your **Azure OpenAI resource**
3. Go to **Keys and Endpoint**
4. Copy:
   - **Endpoint** (e.g., `https://your-resource.openai.azure.com/`)
   - **Key 1** or **Key 2**

### Step 2: Deploy Required Models

You need TWO model deployments:

#### GPT-4o Deployment (for orchestration and synthesis)
1. Go to **Azure OpenAI Studio** → **Deployments**
2. Click **Create new deployment**
3. Select **gpt-4o** model
4. Name it: `gpt-4o` (or your preferred name)
5. Deploy

#### Text Embedding Deployment (for semantic search)
1. Create another deployment
2. Select **text-embedding-ada-002** model
3. Name it: `text-embedding-ada-002`
4. Deploy

**Save the deployment names** - you'll need them for configuration!

---

## Databricks Setup

### Step 1: Get Databricks Workspace Details

1. Go to your Databricks workspace
2. Copy the **Workspace URL** (e.g., `https://your-workspace.databricks.com`)
3. Go to **Settings** → **User** → **Access Tokens**
4. Click **Generate New Token**
5. Copy and save the token securely

### Step 2: Create/Get SQL Warehouse

#### Find existing SQL Warehouse:
1. Go to **SQL Warehouses** in Databricks
2. Select your warehouse (or create one if none exists)
3. Copy the **Warehouse ID**:
   - Click on the warehouse
   - Look at the URL: `sql/warehouses/<warehouse-id>`
   - Or go to **Connection Details** → copy the **HTTP Path** → extract the ID

#### Create new SQL Warehouse (if needed):
1. Click **Create SQL Warehouse**
2. Name: `Multi-Agent-SQL-Warehouse`
3. Cluster size: **2X-Small** (for testing) or larger (for production)
4. Auto-stop: **15 minutes**
5. Click **Create**
6. Copy the **Warehouse ID**

### Step 3: Set Up Unity Catalog

#### Verify Unity Catalog access:
1. Go to **Data** → **Catalog Explorer**
2. You should see at least one catalog (e.g., `main`)
3. Navigate to a schema (e.g., `default`)
4. Note the **catalog name** and **schema name**

#### Identify tables for analysis:
1. List tables you want the agent to query
2. Example: `sales_data`, `customer_data`, `product_data`
3. Make sure you have **SELECT** permission on these tables

### Step 4: Create Genie Space

#### What is Genie?
Genie is Databricks' natural language to SQL service. It converts questions into SQL queries.

#### Create Genie Space:
1. Go to **Genie** in Databricks navigation
2. Click **Create Genie Space**
3. Name: `Multi-Agent-Space`
4. Add instructions (optional):
   ```
   You are a SQL expert. Generate accurate SQL queries for Unity Catalog.
   Use the main catalog and default schema unless specified otherwise.
   ```
5. Select **tables** that Genie can access
6. Click **Create**
7. Go to **Settings** → Copy the **Space ID**

---

## Azure Blob Storage Setup

### Step 1: Get Connection String

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your **Storage Account**
3. Go to **Access keys**
4. Copy **Connection string** (from key1 or key2)

### Step 2: Create Containers (or note existing ones)

The system needs 3 containers (or use 1 container with prefixes):

**Option A: Separate Containers**
- `agent-cache` - for SQL query cache
- `agent-rag-docs` - for RAG documents
- `agent-eda-results` - for table metadata

**Option B: Single Container with Prefixes**
- Container: `reservoir`
- Prefixes: `adm/CXEngine/agent-cache`, `adm/CXEngine/rag-docs`, etc.

The system will **auto-create** containers if they don't exist.

---

## Configuration

### Step 1: Create .env File

```bash
# Copy the example
cp .env.example .env

# Edit with your preferred text editor
nano .env    # Linux/Mac
notepad .env # Windows
```

### Step 2: Fill in Azure OpenAI Configuration

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-actual-api-key-here
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o              # Your deployment name
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
```

### Step 3: Fill in Databricks Configuration

```bash
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=your-databricks-token-here
DATABRICKS_SQL_WAREHOUSE_ID=your-warehouse-id-here   # ⚠️ CRITICAL

GENIE_SPACE_ID=your-genie-space-id-here
```

**🔴 IMPORTANT:** `DATABRICKS_SQL_WAREHOUSE_ID` is **REQUIRED**. Without it, SQL queries will fail!

### Step 4: Fill in Unity Catalog Configuration

```bash
UNITY_CATALOG_NAME=main         # Your catalog name
UNITY_CATALOG_SCHEMA=default    # Your schema name
UNITY_CATALOG_TABLES=sales_data,customer_data,product_data  # Comma-separated, NO quotes!
```

**⚠️ IMPORTANT:** Do NOT use quotes around table names!
- ✅ CORRECT: `UNITY_CATALOG_TABLES=table1,table2,table3`
- ❌ WRONG: `UNITY_CATALOG_TABLES='table1','table2','table3'`

### Step 5: Fill in Azure Storage Configuration

```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

# Option A: Separate containers
AZURE_STORAGE_CONTAINER_CACHE=agent-cache
AZURE_STORAGE_CONTAINER_RAG=agent-rag-docs
AZURE_STORAGE_CONTAINER_EDA=agent-eda-results

# Option B: Single container with prefixes
AZURE_STORAGE_CONTAINER_CACHE=reservoir/adm/CXEngine/agent-cache
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/rag-docs
AZURE_STORAGE_CONTAINER_EDA=reservoir/adm/CXEngine/eda-results
```

### Step 6: Fill in MLflow Configuration

```bash
MLFLOW_EXPERIMENT_NAME=/Users/your-email@company.com/multi-agent
MLFLOW_TRACKING_ENABLED=true
```

**Format:** Must start with `/Users/` for Databricks workspace tracking.

---

## Validation

### Step 1: Run Validation Script

This is the **MOST IMPORTANT** step before using the system!

```bash
python validate_setup.py
```

### Step 2: Review Output

The script checks 10 areas:

1. ✅ Configuration loading
2. ✅ Azure OpenAI configuration and connection
3. ✅ Databricks configuration and connection
4. ✅ SQL Warehouse access
5. ✅ Unity Catalog access (catalog, schema, tables)
6. ✅ Azure Blob Storage configuration and containers
7. ✅ Genie Space configuration
8. ✅ RAG configuration
9. ✅ MLflow configuration
10. ✅ Python dependencies

### Step 3: Fix Any Errors

If validation fails:

1. **Read the error messages carefully**
2. **Fix the configuration** in `.env`
3. **Re-run validation** until all checks pass

**Exit Codes:**
- `0` - All validations passed ✅
- `1` - Critical errors (system won't work) ❌
- `2` - Warnings only (system may work with limitations) ⚠️

---

## First Run

### Option 1: CLI Mode (Interactive)

```bash
python src/main.py
```

This starts an interactive CLI where you can ask questions.

**Example Session:**
```
╔═══════════════════════════════════════════════════════════╗
║   Multi-Agent Orchestrator v1.0.0                         ║
║   Environment: production                                 ║
╚═══════════════════════════════════════════════════════════╝

📊 Analyzing Unity Catalog tables...
✓ Analyzed 3 tables in 12.3s

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

### Option 2: Python API

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

print(result["answer"])

# Cleanup
orchestrator.cleanup()
```

---

## Troubleshooting

### Common Issues

#### 1. "Configuration loading failed"
**Cause:** Syntax error in `.env` file
**Fix:**
- Check for typos in variable names
- Make sure no spaces around `=`
- Don't use quotes for comma-separated values

#### 2. "Databricks connection test failed"
**Causes:**
- Invalid token
- Incorrect workspace URL
- Token expired
- Network/firewall issues

**Fix:**
- Regenerate token in Databricks
- Verify workspace URL format: `https://your-workspace.databricks.com`
- Check network connectivity

#### 3. "SQL Warehouse ID not configured"
**Cause:** Missing `DATABRICKS_SQL_WAREHOUSE_ID` in `.env`
**Fix:** Add the SQL Warehouse ID (see [Databricks Setup](#step-2-createget-sql-warehouse))

#### 4. "Cannot access table"
**Causes:**
- Table doesn't exist
- User lacks SELECT permission
- Wrong catalog/schema name

**Fix:**
- Verify table exists in Databricks
- Check permissions
- Verify `UNITY_CATALOG_NAME` and `UNITY_CATALOG_SCHEMA` values

#### 5. "Azure Storage connection test failed"
**Causes:**
- Invalid connection string
- Storage account deleted
- Network issues

**Fix:**
- Regenerate connection string in Azure Portal
- Verify storage account exists
- Check network connectivity

#### 6. "Genie query failed"
**Causes:**
- Invalid Genie Space ID
- Genie Space not configured
- Query too complex

**Fix:**
- Verify Genie Space ID
- Check Genie Space has access to required tables
- Try simpler queries first

### Getting Help

1. **Check logs:** `logs/app.log`
2. **Run diagnostics:** `python comprehensive_diagnostics.py`
3. **Review docs:** `CLAUDE.md` for architecture details
4. **Check gaps:** `GAP_ANALYSIS.md` for known issues

---

## Next Steps

Once validation passes:

1. ✅ **Run the system:** `python src/main.py`
2. ✅ **Test with simple queries:** Start with basic questions
3. ✅ **Add RAG documents:** Upload PDFs/docs to Azure Blob (RAG container)
4. ✅ **Monitor MLflow:** View experiments in Databricks
5. ✅ **Review caching:** Check cache performance metrics
6. ✅ **Scale up:** Increase SQL Warehouse size if needed

---

## Support

For issues or questions:

1. Review `CLAUDE.md` for architecture details
2. Check `GAP_ANALYSIS.md` for known limitations
3. Review `PROGRESS.md` for development status

---

**Last Updated:** 2026-02-06
**Version:** 1.0.0
**Status:** Production-Ready
