# Agent Skills and Capabilities

This document describes the skills and capabilities of each agent in the Multi-Agent Orchestrator system.

---

## 🧠 Orchestrator Agent

**Purpose:** Main coordinator and decision maker

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **analyze_question** | Understand user intent and required resources | Question string | Analysis dict |
| **create_plan** | Generate execution plan with steps | Question + context | Plan object |
| **route_to_agent** | Route task to appropriate agent | Task description | Agent selection |
| **replan_on_failure** | Create new plan when previous fails | Failed plan + execution log | New plan |
| **detect_ambiguity** | Identify unclear or ambiguous queries | Question | Boolean + confidence |
| **coordinate_agents** | Manage multi-agent workflows | Plan | Execution results |

### Example Use Cases

1. **Simple Query:** "What were sales last month?"
   - Route directly to Genie

2. **Complex Query:** "Compare sales trends with customer satisfaction scores from uploaded reports"
   - Step 1: RAG agent retrieves customer satisfaction from documents
   - Step 2: Genie queries sales data
   - Step 3: Synthesis combines both

3. **Ambiguous Query:** "Show me the data"
   - Triggers human-in-loop for clarification

---

## 📊 Genie Agent

**Purpose:** Execute SQL queries via Databricks Genie

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **natural_language_to_sql** | Convert NL question to SQL | NL question | SQL query + results |
| **query_unity_catalog** | Query tables in Unity Catalog | SQL/NL | Data rows |
| **semantic_caching** | Cache and retrieve similar queries | Query | Cached results (if hit) |
| **result_formatting** | Format query results | Raw data | Structured response |
| **retry_on_failure** | Exponential backoff retry | Failed query | Result or error |

### Supported Query Types

- ✅ Aggregations (SUM, AVG, COUNT)
- ✅ Filters (WHERE conditions)
- ✅ Joins (multi-table queries)
- ✅ Top-N queries (ORDER BY + LIMIT)
- ✅ Time-series queries (date ranges)
- ✅ Group by analytics

### Example Queries

```
"What were our top 5 products by revenue last quarter?"
→ SELECT product_name, SUM(revenue) as total_revenue
  FROM sales_data
  WHERE quarter = 'Q4'
  GROUP BY product_name
  ORDER BY total_revenue DESC
  LIMIT 5

"Show me average customer lifetime value by region"
→ SELECT region, AVG(lifetime_value) as avg_ltv
  FROM customer_data
  GROUP BY region
```

---

## 📋 Table Understanding Agent

**Purpose:** Discover and understand Unity Catalog tables

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **analyze_table_schema** | Extract table structure | Table name | Columns, types, comments |
| **compute_statistics** | Calculate table statistics | Table name | Row count, distinct values |
| **sample_data** | Get representative rows | Table name | Sample rows |
| **semantic_search** | Find relevant tables | NL description | Matching tables |
| **generate_description** | Create human-readable table summary | Table metadata | Description string |
| **suggest_tables** | Recommend tables for query | User question | Ranked table list |

### Example Use Cases

1. **Table Discovery:** "What tables contain customer information?"
   - Searches vector store for "customer"
   - Returns: customer_data, customer_orders, customer_feedback

2. **Column Discovery:** "Which table has email addresses?"
   - Analyzes all table schemas
   - Returns: customer_data (email column)

3. **Data Preview:** "What does the sales_data table look like?"
   - Returns: schema + sample rows + statistics

---

## 📄 RAG Agent

**Purpose:** Process documents and provide context

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **auto_process_documents** | Monitor and process new files | File path | Processed chunks |
| **parse_documents** | Extract text from various formats | File (PDF/DOCX/CSV) | Text content |
| **chunk_text** | Split text into semantic chunks | Text | Chunks |
| **embed_chunks** | Generate embeddings | Text chunks | Vectors |
| **semantic_search** | Find relevant document chunks | Query | Top-K chunks |
| **summarize_documents** | Create document summaries | Document | Summary |

### Supported File Types

| Format | Extension | Support Level |
|--------|-----------|---------------|
| PDF | `.pdf` | ✅ Full |
| Word | `.docx`, `.doc` | ✅ Full |
| Excel | `.xlsx`, `.xls` | ✅ Full (converts to text) |
| PowerPoint | `.pptx`, `.ppt` | ✅ Full |
| CSV | `.csv` | ✅ Full |
| Text | `.txt` | ✅ Full |

### Example Use Cases

1. **Policy Question:** "What's our refund policy?"
   - Searches through uploaded policy documents
   - Returns: Relevant sections from refund_policy.pdf

2. **Report Analysis:** "What does the Q4 report say about churn?"
   - Searches Q4_report.docx
   - Returns: Churn analysis section

3. **Data Context:** "Explain the columns in this CSV"
   - Reads uploaded data_dictionary.csv
   - Returns: Column descriptions

---

## ✨ Synthesis Agent

**Purpose:** Combine results into coherent answers

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **combine_sources** | Merge data from multiple agents | Agent results | Unified context |
| **format_answer** | Create human-readable response | Raw data | Formatted answer |
| **add_context** | Enrich answer with background | Answer + metadata | Enhanced answer |
| **cite_sources** | Add source attribution | Answer + sources | Answer with citations |
| **highlight_insights** | Extract key takeaways | Data | Key insights |

### Synthesis Patterns

**Pattern 1: Data + Context**
```
Input:
- Genie: Sales data (numbers)
- RAG: Industry trends document

Output:
"Your sales of $1.2M represent a 15% increase. According to
the industry trends report, the average growth rate is 8%,
meaning you're outperforming the market."
```

**Pattern 2: Multi-Table Join**
```
Input:
- Genie Query 1: Customer data
- Genie Query 2: Order data

Output:
"Based on the customer and order tables, here are the top
customers by total order value..."
```

**Pattern 3: Explanation + Data**
```
Input:
- Table Understanding: Schema info
- Genie: Query results

Output:
"The sales_data table contains transactions from 2020-2024.
Here are last month's results: [data]"
```

---

## 👤 Human-in-Loop Agent

**Purpose:** Handle clarifications and confirmations

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **ask_clarification** | Request more information | Question | User response |
| **ask_confirmation** | Confirm before action | Action description | Boolean |
| **provide_suggestions** | Offer choices to user | Suggestion list | User selection |
| **notify_user** | Display information | Message | Acknowledgment |
| **present_choices** | Multiple choice question | Options list | Selected option |

### Interaction Patterns

**Pattern 1: Ambiguous Query**
```
User: "Show me the data"

System: "I have access to several tables:
1. sales_data - Product sales by quarter
2. customer_data - Customer demographics
3. product_data - Product catalog

Which would you like to see?"

User: "Sales data"

System: [Proceeds with sales_data query]
```

**Pattern 2: Confirmation**
```
User: "Delete all records from last year"

System: "⚠️ This will delete approximately 10,000 records
from the sales_data table. This action cannot be undone.

Proceed? (yes/no)"

User: "no"

System: "Action cancelled."
```

**Pattern 3: Progressive Refinement**
```
User: "Show me customer trends"

System: "I can analyze customer trends by:
1. Revenue
2. Order frequency
3. Product categories
4. Geographic region

What would you like to focus on?"

User: "Revenue"

System: [Analyzes customer revenue trends]
```

---

## 💾 Supporting Services

### Smart Cache Service

**Skills:**
- Semantic similarity matching
- TTL-based expiration
- Vector-based search
- Tag-based filtering

### Vector Store Service

**Skills:**
- FAISS indexing
- Similarity search
- Persistence to disk
- Multi-index management

### MLflow Tracker

**Skills:**
- Experiment tracking
- Metric logging
- Artifact storage
- Run comparison

### File Monitor Service

**Skills:**
- Real-time file watching
- Pattern matching
- Event handling
- Batch processing

---

## 🔄 Skill Combinations

### Common Workflows

**Workflow 1: New User Query**
```
1. Orchestrator: analyze_question
2. Orchestrator: create_plan
3. Table Understanding: search_tables
4. Genie: natural_language_to_sql
5. Synthesis: combine_sources
6. Synthesis: format_answer
```

**Workflow 2: Document-Enhanced Query**
```
1. Orchestrator: analyze_question
2. RAG: semantic_search (find relevant docs)
3. Genie: query_unity_catalog
4. Synthesis: combine_sources (data + document context)
5. Synthesis: format_answer
```

**Workflow 3: Error Recovery**
```
1. Genie: query fails (table not found)
2. Orchestrator: detect_error
3. Orchestrator: replan_on_failure
4. Table Understanding: search_tables
5. Genie: retry with correct table
6. Success
```

---

## 📊 Skill Matrix

| Agent | Planning | Execution | Analysis | Synthesis | Caching | Human Interaction |
|-------|----------|-----------|----------|-----------|---------|-------------------|
| **Orchestrator** | ✅✅✅ | ✅ | ✅✅ | - | - | ✅ |
| **Genie** | - | ✅✅✅ | - | - | ✅✅✅ | - |
| **Table Understanding** | - | ✅✅ | ✅✅✅ | - | ✅ | - |
| **RAG** | - | ✅✅✅ | ✅ | - | ✅ | - |
| **Synthesis** | - | - | ✅ | ✅✅✅ | - | - |
| **Human Loop** | - | - | - | - | - | ✅✅✅ |

Legend: ✅ = Basic, ✅✅ = Intermediate, ✅✅✅ = Advanced

---

## 🎯 Future Skills

### Planned Enhancements

1. **Orchestrator:**
   - Parallel agent execution
   - A/B testing of strategies
   - Cost optimization

2. **Genie:**
   - Query optimization suggestions
   - Result streaming
   - Incremental updates

3. **Table Understanding:**
   - Auto-relationship detection
   - Data quality scoring
   - Schema evolution tracking

4. **RAG:**
   - Multi-modal support (images, tables)
   - Document versioning
   - Citation extraction

5. **Synthesis:**
   - Chart/graph generation
   - Multi-language support
   - Sentiment analysis

---

## 📚 References

For detailed implementation, see:
- CLAUDE.md - Complete architecture guide
- PROGRESS.md - Development status
- Source code in `src/agents/`

---

**Version:** 1.0.0
**Last Updated:** 2026-02-05
