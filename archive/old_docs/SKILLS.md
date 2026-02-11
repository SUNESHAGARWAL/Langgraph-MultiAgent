# Agent Skills and Capabilities

**Version:** 2.0.0
**Date:** 2026-02-06
**Architecture:** Multi-Agent Supervisor Pattern

This document describes the skills and capabilities of each agent in the Multi-Agent Supervisor system.

---

## 🧠 Supervisor Agent (Orchestrator)

**Purpose:** Central coordinator that routes to specialist agents

**File:** `src/agent.py::create_supervisor_agent()`

### Core Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **analyze_question** | Understand user intent | Question string | Analysis |
| **route_to_specialist** | Select appropriate agent | Analysis | Agent name |
| **coordinate_flow** | Manage multi-step workflows | State | Updated state |
| **replan_on_failure** | Create new approach when stuck | Execution log | New routing decision |
| **iteration_tracking** | Prevent infinite loops | State | Iteration count |
| **human_escalation** | Ask for help when stuck | State | Human request |

### Routing Decisions

```
For data/SQL queries → SQL_Specialist
For document/policy questions → document_search
If unsure or need clarification → HUMAN
When complete answer ready → FINISH (→ synthesis)
```

### Example Use Cases

**1. Simple SQL Query**
```
User: "What were sales last quarter?"
Supervisor: Routes to SQL_Specialist → FINISH → Synthesis
Iterations: 2
```

**2. Multi-Agent Coordination**
```
User: "Compare Q4 sales against policy targets"
Supervisor:
  → SQL_Specialist (get sales)
  → document_search (get targets)
  → FINISH → Synthesis
Iterations: 3
```

**3. Replanning**
```
User: "What's our customer churn rate?"
Supervisor:
  Iteration 1: SQL_Specialist (fails - no churn_rate column)
  Iteration 2: Replan → SQL_Specialist (calculate from activity)
  Iteration 3: FINISH → Synthesis
```

**4. Human Escalation**
```
User: "Show me the data"
Supervisor: Ambiguous → Routes to HUMAN
```

---

## 📊 SQL Specialist (Genie Agent)

**Purpose:** Execute SQL queries on Unity Catalog via Databricks Genie

**File:** `src/agent.py::create_genie_agent()`

### Core Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **natural_language_to_sql** | Convert question to SQL | NL question | SQL + results |
| **query_execution** | Execute on Unity Catalog | SQL | Data rows |
| **result_formatting** | Format as markdown table | Raw data | Markdown string |
| **context_understanding** | Use Genie Space context | Question + tables | Optimized query |

### Supported Query Types

- ✅ **Aggregations:** SUM, AVG, COUNT, MIN, MAX
- ✅ **Filtering:** WHERE conditions, date ranges
- ✅ **Grouping:** GROUP BY with multiple dimensions
- ✅ **Sorting:** ORDER BY, LIMIT (Top-N)
- ✅ **Joins:** Multi-table queries (if configured in Genie Space)
- ✅ **Time-series:** Date/time analysis, trends

### Example Queries

```sql
"What were our top 5 products by revenue last quarter?"
→ SELECT product_name, SUM(revenue) as total_revenue
  FROM sales_data
  WHERE quarter = 'Q4 2025'
  GROUP BY product_name
  ORDER BY total_revenue DESC
  LIMIT 5

"Show me average customer lifetime value by region"
→ SELECT region, AVG(lifetime_value) as avg_ltv
  FROM customer_data
  GROUP BY region
  ORDER BY avg_ltv DESC

"What's the monthly revenue trend for 2025?"
→ SELECT DATE_TRUNC('month', order_date) as month,
         SUM(revenue) as monthly_revenue
  FROM sales_data
  WHERE YEAR(order_date) = 2025
  GROUP BY month
  ORDER BY month
```

### Configuration

```python
GenieAgent(
    genie_space_id=config.databricks.genie_space_id,
    genie_agent_name="SQL_Specialist",
    client=workspace_client,  # WorkspaceClient for auth
    return_pandas=False,      # Returns markdown tables
)
```

**Available Tables:** Configured via `UNITY_CATALOG_TABLES` env var

---

## 📄 Document Search Specialist (RAG Agent)

**Purpose:** Retrieve relevant information from uploaded documents

**File:** `src/agent.py::create_rag_agent()`

### Core Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **semantic_search** | Find relevant document chunks | Query | Top-K chunks |
| **document_parsing** | Extract text from files | File path | Text content |
| **text_chunking** | Split into semantic chunks | Text | Chunks (1000 chars) |
| **embedding_generation** | Generate vector embeddings | Text | Vectors |
| **similarity_matching** | Match query to documents | Query + threshold | Relevant chunks |

### Supported File Types

| Format | Extension | Status |
|--------|-----------|--------|
| **PDF** | `.pdf` | ✅ Full support |
| **Word** | `.docx` | ✅ Full support |
| **Text** | `.txt` | ✅ Full support |
| **CSV** | `.csv` | ✅ Full support |
| **Excel** | `.xlsx` | ✅ Full support |
| **PowerPoint** | `.pptx` | ✅ Full support |

### Document Processing

**Setup:**
```bash
# Add documents to directory
mkdir -p data/documents
cp policies/*.pdf data/documents/
cp reports/*.docx data/documents/

# Restart agent to load documents
python src/main.py
```

**Processing Flow:**
```
1. Load documents from data/documents/
2. Split into chunks (1000 chars, 200 overlap)
3. Generate embeddings (Azure OpenAI)
4. Store in FAISS vector store
5. Ready for retrieval (top-5 most relevant)
```

### Example Use Cases

**1. Policy Question**
```
User: "What's our refund policy?"
RAG: Searches documents → Returns relevant sections
Output: "According to the refund_policy.pdf, customers have 30 days..."
```

**2. Report Analysis**
```
User: "What does the Q4 report say about churn?"
RAG: Searches Q4_report.docx → Returns churn analysis section
Output: "The Q4 2025 report indicates churn rate of 12.5%..."
```

**3. Combined Query**
```
User: "Compare our sales to industry benchmarks"
Supervisor:
  → SQL_Specialist (get our sales)
  → document_search (find industry benchmark doc)
  → Synthesis (compare both)
```

### Configuration

```python
# Chunking
chunk_size=1000
chunk_overlap=200

# Retrieval
top_k=5
similarity_threshold=0.7

# Embedding
model=text-embedding-ada-002 (Azure OpenAI)
```

---

## ✨ Synthesis Agent

**Purpose:** Combine results from multiple specialists into coherent final answer

**File:** `src/agent.py::create_synthesis_agent()`

### Core Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **combine_sources** | Merge data from specialists | Agent results | Unified context |
| **format_answer** | Create human-readable response | Raw data | Formatted answer |
| **add_citations** | Include source attribution | Answer | Answer + sources |
| **highlight_insights** | Extract key findings | Data | Key insights |
| **markdown_formatting** | Structure response nicely | Text | Formatted markdown |

### Synthesis Patterns

**Pattern 1: Single Source (SQL)**
```
Input:
- SQL_Specialist: "Top 5 products: A ($1.2M), B ($980K)..."

Output:
"Based on the sales data, here are the top 5 products by revenue:

1. Product A - $1.2M
2. Product B - $980K
3. Product C - $850K
4. Product D - $720K
5. Product E - $680K

Sources: Unity Catalog (sales_data table)"
```

**Pattern 2: SQL + Documents**
```
Input:
- SQL_Specialist: "Q4 revenue: $2.3M"
- document_search: "Policy target: $2.0M"

Output:
"**Q4 2025 Performance Analysis:**

Revenue: $2.3M
Target: $2.0M (from company policy)
Performance: Exceeded target by 15% ($300K above target)

**Sources:**
- Unity Catalog: sales_data table
- Document: Q4_2025_Sales_Policy.pdf"
```

**Pattern 3: Multi-Step SQL**
```
Input:
- SQL_Specialist (1): "Customer count: 1,500"
- SQL_Specialist (2): "Average order value: $450"

Output:
"**Customer Analytics:**

Total Customers: 1,500
Average Order Value: $450
Estimated Total Revenue: $675K

Sources: Unity Catalog (customer_data, order_data)"
```

### Configuration

```python
# Lower temperature for consistent synthesis
temperature=0.3

# System prompt emphasizes:
# - Combining results
# - Citing sources
# - Markdown formatting
# - Being concise but complete
```

---

## 👤 Human-in-Loop Agent

**Purpose:** Handle clarifications when system is stuck

**File:** `src/agent.py::create_human_node()`

### Core Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **ask_clarification** | Request more information | Question | User response |
| **notify_user** | Display message | Message | Acknowledgment |
| **pause_execution** | Wait for human input | State | Pause |

### Trigger Conditions

**1. Ambiguous Query**
```
User: "Show me the data"
Supervisor: → HUMAN (unclear which data)
```

**2. Iteration Limit**
```
After 5 iterations without success → HUMAN
"I've tried multiple approaches but need your help..."
```

**3. Explicit Routing**
```
Supervisor determines query is unclear → HUMAN
```

### Production Customization

Replace CLI input with real systems:

**Option 1: Webhook**
```python
response = requests.post(
    "https://api.example.com/ask-human",
    json={"question": "...", "thread_id": "..."}
)
clarification = response.json()["answer"]
```

**Option 2: Queue System**
```python
queue.publish("human-input-needed", {"question": "..."})
clarification = queue.wait_for_response(timeout=300)
```

**Option 3: Slack/Teams**
```python
slack.send_message(
    channel="agent-questions",
    text="Need clarification: ..."
)
clarification = slack.wait_for_reply(timeout=300)
```

---

## 🔄 Multi-Agent Workflows

### Workflow 1: Simple SQL Query

```
Step 1: supervisor (analyze + route)
Step 2: SQL_Specialist (execute query)
Step 3: supervisor (review results)
Step 4: synthesis (format answer)

Iterations: 2
Typical Latency: 5-10s
```

### Workflow 2: Document-Enhanced Query

```
Step 1: supervisor (analyze + route)
Step 2: SQL_Specialist (get data)
Step 3: supervisor (needs context)
Step 4: document_search (find relevant docs)
Step 5: supervisor (combine)
Step 6: synthesis (merge SQL + docs)

Iterations: 4
Typical Latency: 10-15s
```

### Workflow 3: Replanning After Failure

```
Iteration 1:
  supervisor → SQL_Specialist (fails: table not found)

Iteration 2:
  supervisor (replan) → SQL_Specialist (try different approach)

Iteration 3:
  supervisor → synthesis (success!)

Total Iterations: 3
```

### Workflow 4: Human Escalation

```
Iteration 1-5: Various attempts fail
Iteration 6: supervisor → HUMAN
  "I've tried multiple approaches but need your help..."

[Wait for human response]

Iteration 7: supervisor (with clarification) → continue
```

---

## 📊 Agent Capabilities Matrix

| Agent | Routing | SQL Execution | Document Search | Synthesis | Human Interaction |
|-------|---------|---------------|-----------------|-----------|-------------------|
| **Supervisor** | ✅✅✅ | - | - | - | ✅ |
| **SQL_Specialist** | - | ✅✅✅ | - | - | - |
| **document_search** | - | - | ✅✅✅ | - | - |
| **Synthesis** | - | - | - | ✅✅✅ | - |
| **Human** | - | - | - | - | ✅✅✅ |

**Legend:** ✅ = Basic, ✅✅ = Intermediate, ✅✅✅ = Advanced

---

## 🎯 Customization & Extension

### Add New Specialist Agent

**Example: Web Search Agent**

```python
def create_web_search_agent():
    """Add web search capability"""
    from langchain_community.tools import DuckDuckGoSearchRun

    search_tool = DuckDuckGoSearchRun()

    return create_retriever_tool(
        search_tool,
        "web_search",
        """Web search specialist. Use for:
        - Current events and news
        - External information
        - General knowledge

        Returns: Search results from the web"""
    )

# Add to graph
workflow.add_node("web_search", ToolNode([web_search_agent]))

# Update supervisor routing
# Add: "For current events → web_search"
```

### Add Custom State Fields

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str
    iterations: int
    final_answer: str

    # Custom fields
    confidence: float      # Track confidence
    sources: list[str]     # Track all sources
    user_id: str          # Track user
```

### Add Result Grading

```python
def create_grader_node():
    """Grade specialist results for relevance"""
    model = AzureChatOpenAI(...)

    def grader_node(state: AgentState):
        # Grade result
        grade = model.invoke([
            SystemMessage("Grade result: RELEVANT or NOT_RELEVANT"),
            *state["messages"]
        ])

        if grade == "NOT_RELEVANT":
            return {"next_agent": "supervisor"}  # Replan
        else:
            return {"next_agent": "synthesis"}   # Continue

    return grader_node

# Add to graph
workflow.add_node("grader", create_grader_node())
workflow.add_edge("SQL_Specialist", "grader")
```

---

## 📚 Best Practices

### 1. Question Formulation

**✅ Good:**
- "What were our top 5 products by revenue in Q4 2025?"
- "Compare Q4 sales against company policy targets"
- "What does the customer churn report say?"

**❌ Poor:**
- "Show me data" (too vague)
- "Give me everything" (too broad)
- "What happened?" (no context)

### 2. Document Organization

**Recommended Structure:**
```
data/documents/
├── policies/
│   ├── refund_policy.pdf
│   └── sales_targets_2025.pdf
├── reports/
│   ├── Q4_2025_analysis.docx
│   └── customer_churn_report.pdf
└── technical/
    └── api_documentation.pdf
```

### 3. Conversation Memory

**Use thread_id for:**
- Multi-turn conversations
- Follow-up questions
- Context retention across queries

**Start fresh for:**
- New users
- Different topics
- Independent queries

---

## 📖 References

**Documentation:**
- **CLAUDE.md** - Complete architecture guide
- **REFERENCE.md** - API reference and examples
- **README.md** - Quick start guide

**Implementation:**
- **src/agent.py** - All agent implementations
- **src/main.py** - CLI interface

**External Resources:**
- **LangGraph:** https://langchain-ai.github.io/langgraph/
- **Databricks Genie:** https://docs.databricks.com/generative-ai/agent-framework/multi-agent-genie
- **databricks-langchain:** https://pypi.org/project/databricks-langchain/

---

**Version:** 2.0.0
**Date:** 2026-02-06
**Status:** ✅ Production-Ready
