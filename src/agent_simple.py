"""
Simplified Multi-Agent System with RAG and Smart Caching
=========================================================

A streamlined multi-agent orchestrator that:
1. RAG: Answer from documents OR enrich context
2. Reads Unity Catalog schemas
3. Analyzes questions for answerability
4. Plans and formats clean queries
5. Executes via Genie (with smart caching)
6. Synthesizes results

Features:
- Dual-purpose RAG (standalone Q&A + context enrichment)
- Smart SQL caching (semantic similarity)
- NO validation loops - trust the results!

Author: Claude Code
Version: 5.1.0-rag-caching
Date: 2026-02-12
"""

import operator
from typing import Any, Dict, List, Annotated, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from databricks.sdk import WorkspaceClient
from databricks_langchain import GenieAgent

from src.core.config import config
from src.utils.logging import get_logger

# RAG and Caching imports
from src.utils.embeddings import initialize_embedding_service, get_embedding_service
from src.services.rag_store import initialize_rag_store, get_rag_store
from src.services.smart_cache import initialize_sql_cache, get_sql_cache
from src.utils.parsers import load_documents_from_directory

logger = get_logger(__name__)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class AgentState(TypedDict):
    """State passed between agents with explicit workflow tracking"""
    # Message history (LangGraph operator.add reducer)
    messages: Annotated[list[BaseMessage], operator.add]

    # Workflow stage tracking (explicit boolean flags)
    rag_checked: bool              # RAG search completed?
    schema_analyzed: bool          # Schema analysis completed?
    query_planned: bool            # Query planning completed?
    genie_executed: bool           # Genie execution completed?

    # Core data fields
    original_question: str         # Store original user question
    schema_info: str              # Unity Catalog schema info
    formatted_query: str          # Query for Genie
    final_answer: str             # Synthesized answer

    # RAG fields (document-based Q&A + context enrichment)
    rag_context: str              # RAG context hints for schema/query
    rag_answer: str               # Direct answer from RAG (standalone mode)
    rag_can_answer: bool          # RAG can answer without Genie
    rag_similarity: float         # Best RAG document similarity

    # Caching fields (smart SQL caching)
    cache_checked: bool           # Cache lookup performed?
    cache_hit: bool               # Query served from cache?
    cached_result: str            # Cached result if hit

    # Routing control
    next_agent: str               # Next agent to route to
    iterations: int               # Iteration counter

    # Analysis results
    is_answerable: bool           # Can question be answered?
    needs_clarification: bool     # Needs user clarification?
    clarification_provided: bool  # User provided clarification?


# ============================================================================
# UNITY CATALOG SCHEMA READER
# ============================================================================

class UnitySchemaReader:
    """
    Reads Unity Catalog table schemas including:
    - Table names
    - Column names, types, comments
    - Table comments
    """

    def __init__(self, workspace_client: WorkspaceClient):
        self.workspace_client = workspace_client
        self.table_api = workspace_client.tables
        self.schema_cache: Dict[str, Dict[str, Any]] = {}

    def read_table_schema(self, full_table_name: str) -> Dict[str, Any]:
        """Read schema for a specific table from Unity Catalog"""
        if full_table_name in self.schema_cache:
            logger.info(f"Using cached schema for {full_table_name}")
            return self.schema_cache[full_table_name]

        try:
            logger.info(f"Reading schema for table: {full_table_name}")
            table_info = self.table_api.get(full_table_name)

            schema_info = {
                "table_name": full_table_name,
                "table_comment": table_info.comment or "No comment",
                "table_type": table_info.table_type.value if table_info.table_type else "UNKNOWN",
                "columns": []
            }

            if table_info.columns:
                for col in table_info.columns:
                    column_info = {
                        "name": col.name,
                        "type": col.type_name.value if col.type_name else "UNKNOWN",
                        "comment": col.comment or "No comment",
                        "nullable": col.nullable if hasattr(col, "nullable") else True
                    }
                    schema_info["columns"].append(column_info)

                logger.info(f"✓ Loaded {len(schema_info['columns'])} columns from {full_table_name}")
            else:
                logger.warning(f"No columns found for {full_table_name}")

            self.schema_cache[full_table_name] = schema_info
            return schema_info

        except Exception as e:
            logger.error(f"Failed to read schema for {full_table_name}: {e}")
            raise

    def read_all_configured_schemas(self) -> str:
        """Read all configured table schemas and format as text"""
        all_schemas = []

        for table_name in config.databricks.unity_tables:
            try:
                schema = self.read_table_schema(table_name)
                formatted = self._format_schema_for_llm(schema)
                all_schemas.append(formatted)
            except Exception as e:
                logger.error(f"Skipping table {table_name}: {e}")
                continue

        return "\n\n".join(all_schemas)

    def _format_schema_for_llm(self, schema: Dict[str, Any]) -> str:
        """Format schema information for LLM consumption"""
        lines = [
            f"Table: {schema['table_name']}",
            f"  Description: {schema['table_comment']}",
            f"  Type: {schema['table_type']}",
            f"  Columns ({len(schema['columns'])}):"
        ]

        for col in schema['columns']:
            lines.append(
                f"    - {col['name']} ({col['type']}): {col['comment']}"
            )

        return "\n".join(lines)


# ============================================================================
# AGENTS
# ============================================================================

def create_schema_analysis_agent(schema_reader: UnitySchemaReader, llm: AzureChatOpenAI):
    """
    Agent that:
    1. Reads Unity Catalog schemas
    2. Analyzes if user question is answerable with available data
    3. Uses semantic understanding (not hardcoded column matching)
    """

    def schema_analysis_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Schema Analysis Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Collect ALL user messages (original + clarifications)
        all_user_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                all_user_messages.append(msg.content)

        if not all_user_messages:
            logger.error("No user messages found")
            return {
                **state,  # Preserve all existing fields
                "next_agent": "human",
                "is_answerable": False,
                "needs_clarification": True,
                "schema_analyzed": False,
                "iterations": iterations + 1
            }

        # Get or store original question
        original_question = state.get("original_question", "")
        if not original_question:
            original_question = all_user_messages[0]

        # Build user context including any clarifications
        if len(all_user_messages) > 1:
            # User provided clarification - include both original and clarification
            user_question = f"""Original question: {original_question}

Additional clarification provided by user: {all_user_messages[-1]}

IMPORTANT: The user has now provided additional details. Re-analyze with this NEW information."""
        else:
            # First time asking
            user_question = original_question

        # Read schemas if not already in state
        schema_info = state.get("schema_info", "")
        if not schema_info:
            logger.info("Reading Unity Catalog schemas...")
            schema_info = schema_reader.read_all_configured_schemas()
            logger.info(f"✓ Loaded schemas for {len(config.databricks.unity_tables)} tables")

        # Get RAG context if available (business definitions, metric calculations)
        rag_context = state.get("rag_context", "")

        # Analyze with LLM using semantic understanding + RAG context + business logic
        analysis_prompt = f"""You are an expert data analyst with deep business intelligence capabilities.

Your task: Understand USER INTENT, intelligently select RELEVANT COLUMNS, and apply BUSINESS LOGIC.

═══════════════════════════════════════════════════════════════════════════════
🧠 INTELLIGENT REASONING RULES
═══════════════════════════════════════════════════════════════════════════════

1. SEMANTIC COLUMN MATCHING (Be Smart, Not Literal!)

   User says "sentiment" → Think: What columns capture emotional/satisfaction data?
   ✓ sentiment_score, customer_satisfaction, nps, csat, feedback_rating, mood_score
   ✗ Don't require exact "sentiment" column name

   User says "conversion rate" → Think: What formula? What columns needed?
   ✓ conversion_rate (if exists) OR calculate: conversions / total_visitors
   ✓ Identify: conversions, purchases, clicks, visits, impressions columns

   User says "revenue by region" → Think: What's needed?
   ✓ revenue/amount/sales columns + geography/region/location columns

2. BUSINESS LOGIC UNDERSTANDING (Calculate Metrics Intelligently!)

   Common Business Metrics and Their Logic:

   • Conversion Rate = (Conversions / Total Visits) × 100
     Columns needed: conversion_count, total_visits OR purchase_count, visitor_count

   • Churn Rate = (Customers Lost / Total Customers) × 100
     Columns needed: churned_customers, total_customers, end_date

   • Average Order Value = Total Revenue / Number of Orders
     Columns needed: revenue, order_count

   • Customer Lifetime Value = Average Order Value × Purchase Frequency × Customer Lifespan
     Columns needed: revenue, order_count, customer_id, first_purchase_date

   • Net Promoter Score (NPS) = % Promoters - % Detractors
     Columns needed: nps_score OR rating/satisfaction (if 0-10 scale)

   IF user asks for a CALCULATED METRIC:
   - Identify which columns are needed for the calculation
   - Check if a pre-calculated column exists (conversion_rate column)
   - If not, identify source columns (conversions, visits)
   - Explain the calculation logic to the user

3. INTELLIGENT COLUMN SELECTION (What Data is ACTUALLY Needed?)

   User: "Show me sentiment for bangalore"

   Your reasoning process:
   Step 1: What's the goal? → Sentiment analysis for a specific city
   Step 2: What columns are needed?
     - Sentiment data: sentiment_score, satisfaction, nps, feedback
     - Location filter: city, location, region, geography
     - Context: date, product, category (helpful for insights)
   Step 3: Which table has ALL these columns?
   Step 4: Select minimal but sufficient columns

   User: "What's our conversion rate last quarter?"

   Your reasoning:
   Step 1: Goal? → Calculate conversion rate for Q3/Q4
   Step 2: Formula? → conversions / total_visitors
   Step 3: Columns needed:
     - Numerator: conversion_count, purchase_count, successful_transactions
     - Denominator: total_visits, visitor_count, session_count
     - Time filter: date, quarter, period
   Step 4: Identify which table has these columns
   Step 5: If missing, ask user OR suggest alternative calculation

4. CONTEXT-AWARE FILTERING (What Filters Make Sense?)

   Think about what filters are NECESSARY vs OPTIONAL:

   Necessary filters (missing = unclear query):
   - Time range for trends: "revenue last month" needs date
   - Location for geo-specific: "bangalore sales" needs city filter
   - Category for segmentation: "mobile phone sales" needs product filter

   Optional filters (can proceed without):
   - Additional breakdowns: "by region" when already have country
   - Minor segments: "for premium customers" when total is fine

5. RAG INTEGRATION (Use Business Knowledge!)
{f'''
   📚 BUSINESS CONTEXT FROM DOCUMENTATION:
   {rag_context}

   Use this context to understand:
   - Column definitions (what nps_score means)
   - Business metric calculations (how conversion is calculated)
   - Data relationships (which tables to join)
   - Business rules (filter criteria, valid ranges)
''' if rag_context else ""}

═══════════════════════════════════════════════════════════════════════════════
📊 ANALYSIS OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

**ANSWERABLE: YES** (if can answer with available columns)
**ANSWERABLE: NEEDS_CLARIFICATION** (if need to narrow down or select table)
**ANSWERABLE: NO** (if truly impossible - no relevant columns exist)

**INTELLIGENT REASONING:**
[Explain your thought process:
 - What is user trying to achieve?
 - Which columns semantically match the intent?
 - What business logic applies?
 - What's the calculation formula if needed?]

**SELECTED COLUMNS AND TABLES:**
Table: [table_name]
Required columns:
  - [column_name]: [why this column? what does it provide?]
  - [column_name]: [purpose in the query]

Optional/context columns:
  - [column_name]: [adds context but not critical]

**BUSINESS LOGIC APPLIED:**
[If calculating a metric, explain the formula and which columns map to it]
Example: "Conversion Rate = conversions / total_visits
         - conversions → conversion_count column
         - total_visits → visitor_count column"

**WHAT'S NEEDED FROM USER:**
[Only ask if TRULY ambiguous - be autonomous when possible!
 - Multiple valid tables? Ask which one
 - Missing critical filter? Ask for it
 - Can make reasonable assumption? DO IT and mention in reasoning]

**CLARIFICATION QUESTIONS (if needed):**
[Smart, specific questions - not generic "what do you want?"
 Example: "I found sentiment data in 2 tables:
          1. pc_sales (product sentiment)
          2. customer_feedback (overall satisfaction)
          Which would you like to analyze?"]

═══════════════════════════════════════════════════════════════════════════════
📁 AVAILABLE SCHEMAS
═══════════════════════════════════════════════════════════════════════════════
{schema_info}

═══════════════════════════════════════════════════════════════════════════════
❓ USER QUESTION
═══════════════════════════════════════════════════════════════════════════════
{user_question}

═══════════════════════════════════════════════════════════════════════════════

Now analyze with INTELLIGENCE and AUTONOMY. Be smart, reason about business logic, select relevant columns!"""

        try:
            response = llm.invoke([
                SystemMessage(content=analysis_prompt),
            ])

            analysis_content = response.content
            logger.info(f"Schema Analysis:\n{analysis_content}")

            # Parse answerability status
            content_upper = analysis_content.upper()

            # Check for different states
            if "ANSWERABLE: NEEDS_CLARIFICATION" in content_upper or "NEEDS CLARIFICATION" in content_upper:
                logger.info("⚠️  Question needs clarification")

                # Extract clarification questions
                clarification = "I need more information to answer your question."
                if "CLARIFICATION QUESTIONS:" in analysis_content:
                    parts = analysis_content.split("CLARIFICATION QUESTIONS:")
                    if len(parts) > 1:
                        clarification = parts[1].strip()

                # Format nice clarification message
                clarification_msg = f"""[Schema Analysis Complete - Needs Clarification]

I found data that matches your question, but I need some clarification:

{clarification}

💡 **Tip:** If you want me to just proceed with reasonable defaults, say "just proceed" or "use defaults"."""

                return {
                    **state,  # Preserve all existing fields
                    "messages": [AIMessage(content=clarification_msg)],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": False,
                    "needs_clarification": True,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

            elif "ANSWERABLE: YES" in content_upper:
                logger.info("✓ Question is answerable with available data")
                return {
                    **state,  # Preserve all existing fields
                    "messages": [AIMessage(content=f"Schema Analysis:\n{analysis_content}")],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": True,
                    "needs_clarification": False,
                    "next_agent": "query_planner",
                    "iterations": iterations + 1
                }

            else:  # ANSWERABLE: NO
                logger.info("✗ Question is NOT answerable - cannot be done with available data")

                # Extract reason
                reason = "This question cannot be answered with the available data."
                if "REASONING:" in analysis_content:
                    parts = analysis_content.split("REASONING:")
                    if len(parts) > 1:
                        reason = parts[1].split("**")[0].strip()

                return {
                    **state,  # Preserve all existing fields
                    "messages": [AIMessage(content=f"I'm sorry, but {reason}")],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": False,
                    "needs_clarification": False,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"Schema analysis failed: {e}", exc_info=True)
            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content=f"Schema analysis error: {str(e)}")],
                "schema_analyzed": False,
                "next_agent": "human",
                "is_answerable": False,
                "needs_clarification": True,
                "iterations": iterations + 1
            }

    return schema_analysis_node


def create_query_planner_agent(llm: AzureChatOpenAI):
    """
    Agent that:
    1. Takes schema analysis results
    2. Formats clean, specific queries for Genie
    3. NO chat history - only formatted questions!
    """

    def query_planner_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Query Planner Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]
        schema_info = state.get("schema_info", "")

        # Get user question and schema analysis
        user_question = None
        schema_analysis = None
        all_user_messages = []

        for msg in messages:
            if isinstance(msg, HumanMessage):
                all_user_messages.append(msg.content)
            if isinstance(msg, AIMessage) and "Schema Analysis" in msg.content and schema_analysis is None:
                schema_analysis = msg.content

        # Get the original question and any clarifications
        original_question = all_user_messages[0] if all_user_messages else None
        latest_user_input = all_user_messages[-1] if all_user_messages else None

        if not original_question:
            logger.error("Missing user question")
            return {
                **state,  # Preserve all existing fields
                "next_agent": "human",
                "iterations": iterations + 1
            }

        # Check if user said "just proceed" or "use defaults"
        use_defaults = False
        if latest_user_input and any(phrase in latest_user_input.lower() for phrase in ["just proceed", "use default", "proceed", "go ahead", "continue anyway"]):
            use_defaults = True
            logger.info("User requested to proceed with defaults")

        # Build context from all user messages
        user_context = f"Original question: {original_question}"
        if len(all_user_messages) > 1 and not use_defaults:
            user_context += f"\n\nAdditional details provided: {latest_user_input}"

        # Get RAG context for business definitions
        rag_context = state.get("rag_context", "")

        planning_prompt = f"""You are an intelligent query planning specialist for Databricks Genie.

Your task: Transform schema analysis into SMART, NATURAL queries using BUSINESS LOGIC.

═══════════════════════════════════════════════════════════════════════════════
🎯 INTELLIGENT QUERY CONSTRUCTION
═══════════════════════════════════════════════════════════════════════════════

1. USE THE COLUMN INTELLIGENCE FROM SCHEMA ANALYSIS

   The schema analysis has already identified:
   - Which specific columns are needed
   - What business logic applies
   - What calculations are required

   YOUR JOB: Convert this intelligence into natural Genie queries

2. BUSINESS METRIC QUERIES (Be Smart About Calculations!)

   Example: User wants "conversion rate"

   Schema Analysis identified:
   - Formula: conversions / total_visits
   - Columns: conversion_count, visitor_count
   - Table: web_analytics

   YOUR QUERY:
   "From the web_analytics table, calculate the conversion rate by dividing
   conversion_count by visitor_count, and show the result as a percentage"

   Example: User wants "NPS score"

   Schema Analysis identified:
   - Column: nps_score (already calculated)
   - Filter: city = bangalore
   - Table: customer_feedback

   YOUR QUERY:
   "Show me the NPS scores from the customer_feedback table for bangalore"

3. INTELLIGENT COLUMN SELECTION (Use What Analysis Found!)

   Example: User asks "sentiment for bangalore"

   Schema Analysis identified:
   - sentiment_score column (main metric)
   - city column (filter)
   - date column (context)
   - product column (additional context)

   YOUR QUERY:
   "From the pc_sales table, show me the sentiment_score for records where
   city is bangalore. Also include the date and product for context."

   DON'T create vague queries! Use the SPECIFIC columns identified.

4. CALCULATED METRICS (Explain the Math to Genie)

   When schema analysis identifies a calculated metric:

   ✓ "Calculate average order value by dividing total_revenue by order_count"
   ✓ "Calculate churn rate as (churned_customers / total_customers) * 100"
   ✓ "Show conversion rate: successful_purchases divided by total_visitors"

   ✗ "Show me the conversion rate" (too vague - Genie might not know the formula)

5. CONTEXT-AWARE FILTERING (Apply Smart Filters)

   Use filters identified in schema analysis:

   - Date ranges: "for October 2025" or "in the last quarter"
   - Location: "where city is bangalore" or "for the bangalore region"
   - Categories: "for product category mobile phones"
   - Conditions: "where sentiment_score is negative" or "rating below 5"

6. RAG-ENHANCED QUERIES (Use Business Definitions!)
{f'''
   📚 BUSINESS KNOWLEDGE FROM DOCUMENTATION:
   {rag_context}

   Use this to:
   - Understand metric definitions
   - Know calculation formulas
   - Apply business rules
   - Use correct terminology
''' if rag_context else ""}

═══════════════════════════════════════════════════════════════════════════════
✅ GOOD vs BAD QUERIES
═══════════════════════════════════════════════════════════════════════════════

GOOD (Specific, intelligent, uses columns from analysis):
✓ "From pc_sales, show sentiment_score and city where city = 'bangalore' and
   date is in October 2025. Include product name for context."

✓ "Calculate conversion rate from web_analytics by dividing conversion_count
   by visitor_count for Q4 2024. Show as percentage."

✓ "From customer_feedback, show the average NPS score grouped by region
   for the last 3 months."

BAD (Vague, no column intelligence):
✗ "Show me sentiment data" (which columns? which table? what filters?)
✗ "Calculate conversion rate" (what formula? which columns?)
✗ "SELECT sentiment_score FROM pc_sales WHERE city = 'bangalore'" (too SQL-like!)

═══════════════════════════════════════════════════════════════════════════════
📥 YOUR INPUTS
═══════════════════════════════════════════════════════════════════════════════

SCHEMA ANALYSIS (WITH COLUMN INTELLIGENCE):
{schema_analysis}

USER CONTEXT:
{user_context}

{"USER WANTS DEFAULTS: " + latest_user_input if use_defaults else ""}

═══════════════════════════════════════════════════════════════════════════════
📤 YOUR OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Create NATURAL, INTELLIGENT queries that:
1. Use the SPECIFIC columns identified in schema analysis
2. Apply business logic and calculations properly
3. Include smart filters and context
4. Are conversational but precise

Format:

**QUERY 1:**
[Natural, intelligent query using specific columns and business logic]

**QUERY 2:**
[Additional query if needed for multi-part questions]

**REASONING:**
[Briefly explain: What columns are you using? What calculation/filter logic?]

═══════════════════════════════════════════════════════════════════════════════

Now create SMART queries using the column intelligence and business logic from the analysis!"""

        try:
            response = llm.invoke([SystemMessage(content=planning_prompt)])
            query_plan = response.content
            logger.info(f"Query Plan:\n{query_plan}")

            # Parse queries
            formatted_queries = []
            if "**QUERY" in query_plan:
                lines = query_plan.split("\n")
                current_query = []
                for line in lines:
                    if line.strip().startswith("**QUERY"):
                        if current_query:
                            formatted_queries.append("\n".join(current_query).strip())
                        current_query = []
                    elif line.strip() and not line.strip().startswith("**"):
                        current_query.append(line.strip())
                if current_query:
                    formatted_queries.append("\n".join(current_query).strip())
            else:
                # Fallback: use entire response
                formatted_queries = [query_plan.strip()]

            # Store formatted queries
            formatted_query_text = "\n\n".join([f"Query {i+1}: {q}" for i, q in enumerate(formatted_queries)])

            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content=f"Query Plan:\n{query_plan}")],
                "formatted_query": formatted_query_text,
                "query_planned": True,
                "next_agent": "genie",
                "iterations": iterations + 1
            }

        except Exception as e:
            logger.error(f"Query planning failed: {e}", exc_info=True)
            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content=f"Query planning error: {str(e)}")],
                "query_planned": False,
                "next_agent": "synthesis",
                "iterations": iterations + 1
            }

    return query_planner_node


def create_genie_executor_node(workspace_client: WorkspaceClient, sql_cache=None):
    """
    Agent that:
    1. Checks smart cache for similar queries
    2. Takes formatted queries
    3. Executes them via Genie (if cache miss)
    4. Caches results
    5. Returns results
    """

    # Initialize Genie agent
    genie_agent = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="SQL_Specialist",
        description="SQL query execution specialist for Unity Catalog",
        client=workspace_client,
        return_pandas=False,
    )

    def genie_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Genie Executor Agent ===")

        iterations = state.get("iterations", 0)
        formatted_query = state.get("formatted_query", "")

        if not formatted_query:
            logger.error("No formatted query found")
            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content="Error: No query to execute")],
                "genie_executed": False,
                "cache_checked": True,
                "cache_hit": False,
                "next_agent": "synthesis",
                "iterations": iterations + 1
            }

        # Check cache first (if enabled)
        if sql_cache:
            try:
                cached_result = sql_cache.get(formatted_query)
                if cached_result:
                    logger.info("✓ Cache HIT - returning cached result")
                    return {
                        **state,
                        "messages": [AIMessage(content=f"[FROM CACHE]\n\n{cached_result}")],
                        "cache_checked": True,
                        "cache_hit": True,
                        "cached_result": cached_result,
                        "genie_executed": True,
                        "next_agent": "synthesis",
                        "iterations": iterations + 1
                    }
                else:
                    logger.info("✗ Cache MISS - executing Genie")
            except Exception as e:
                logger.warning(f"Cache check failed: {e}")


        # Parse individual queries
        queries = []
        if "Query" in formatted_query:
            parts = formatted_query.split("Query")
            for part in parts[1:]:  # Skip first empty part
                # Extract query text after the number and colon
                if ":" in part:
                    query_text = part.split(":", 1)[1].strip()
                    queries.append(query_text)
        else:
            queries = [formatted_query]

        logger.info(f"Executing {len(queries)} query(ies)")

        # Execute each query
        results = []
        for i, query in enumerate(queries):
            try:
                logger.info(f"Executing Query {i+1}: {query[:100]}...")
                result = genie_agent.invoke({"messages": [HumanMessage(content=query)]})

                # Extract result content
                if isinstance(result, dict) and "messages" in result:
                    result_content = result["messages"][-1].content if result["messages"] else "No result"
                else:
                    result_content = str(result)

                results.append(f"**Query {i+1} Result:**\n{result_content}")
                logger.info(f"✓ Query {i+1} completed successfully")

            except Exception as e:
                logger.error(f"Query {i+1} failed: {e}")
                results.append(f"**Query {i+1} Error:**\n{str(e)}")

        # Combine all results
        combined_results = "\n\n".join(results)

        # Cache the result (if caching enabled)
        if sql_cache:
            try:
                sql_cache.set(formatted_query, combined_results)
                logger.info("✓ Result cached for future queries")
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")

        return {
            **state,  # Preserve all existing fields
            "messages": [AIMessage(content=f"Genie Results:\n\n{combined_results}")],
            "cache_checked": True,
            "cache_hit": False,
            "genie_executed": True,
            "next_agent": "synthesis",
            "iterations": iterations + 1
        }

    return genie_node


def create_synthesis_agent(llm: AzureChatOpenAI):
    """
    Agent that:
    1. Takes all results
    2. Synthesizes into final answer
    3. Cites sources
    4. Formats nicely
    """

    def synthesis_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Synthesis Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Extract user question and all results
        user_question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break

        synthesis_prompt = """You are a synthesis specialist.

Your task:
1. Review all the information gathered (schema analysis, query results)
2. Create a clear, comprehensive answer to the user's question
3. Format results nicely (use tables if appropriate)
4. Cite which tables/data sources were used
5. Be concise but complete

If results show errors or no data, explain that clearly.

Now synthesize the information below into a final answer:"""

        try:
            response = llm.invoke([
                SystemMessage(content=synthesis_prompt),
                *messages,
                HumanMessage(content="Please synthesize the above information into a final answer for the user.")
            ])

            final_answer = response.content
            logger.info("✓ Synthesis complete")

            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content=final_answer)],
                "final_answer": final_answer,
                "next_agent": "FINISH",
                "iterations": iterations + 1
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            return {
                **state,  # Preserve all existing fields
                "messages": [AIMessage(content=f"I encountered an error while synthesizing results: {str(e)}")],
                "final_answer": f"Error: {str(e)}",
                "next_agent": "FINISH",
                "iterations": iterations + 1
            }

    return synthesis_node


def create_human_node():
    """
    Agent that handles human clarification requests.
    Loops back to supervisor after displaying clarification question.
    """

    def human_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Human Clarification Required ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get clarification question from last AI message
        clarification_question = "I need more information to answer your question."
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and "clarification" in msg.content.lower():
                clarification_question = msg.content
                break

        # In CLI mode, this will display the clarification and wait for user input
        # The graph will pause here, and when user responds, it loops back to supervisor

        return {
            **state,  # Preserve all existing fields
            "messages": [AIMessage(content=clarification_question)],
            "final_answer": clarification_question,
            "clarification_provided": False,  # Will be set to True when user responds
            "next_agent": "supervisor",  # Loop back to supervisor after user responds
            "iterations": iterations + 1
        }

    return human_node


# ============================================================================
# RAG AGENT (Document Q&A + Context Enrichment)
# ============================================================================

def create_rag_node(rag_store, config):
    """
    RAG agent with dual-purpose mode:
    1. Standalone Q&A: Answer questions directly from documents
    2. Context enrichment: Provide hints to schema/query planners
    """

    def rag_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== RAG Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get user question
        user_question = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break

        if not user_question:
            logger.warning("No user question found for RAG")
            return {
                **state,
                "rag_checked": True,
                "rag_can_answer": False,
                "next_agent": "schema",
                "iterations": iterations + 1
            }

        # Search RAG store for relevant documents
        try:
            results = rag_store.search(
                query=user_question,
                top_k=config.rag.top_k,
                min_similarity=config.rag.min_similarity
            )

            if not results:
                logger.info("No relevant documents found in RAG")
                return {
                    **state,
                    "rag_checked": True,
                    "rag_can_answer": False,
                    "rag_context": "",
                    "next_agent": "schema",
                    "iterations": iterations + 1
                }

            # Get best result
            best_result = results[0]
            best_similarity = best_result.metadata.get("similarity", 0.0)

            logger.info(f"RAG found {len(results)} documents (best similarity: {best_similarity:.3f})")

            # Determine if can answer standalone
            can_answer_standalone = (
                config.rag.enable_standalone_qa and
                best_similarity >= config.rag.standalone_threshold
            )

            if can_answer_standalone:
                # Mode 1: Standalone Q&A - Answer directly from documents
                logger.info(f"✓ RAG answering standalone (similarity: {best_similarity:.3f})")

                # Build answer from top documents
                answer_parts = [f"Based on the available documentation:\n"]
                for i, doc in enumerate(results[:3]):
                    answer_parts.append(f"\n**Source {i+1}** ({doc.metadata.get('filename', 'Unknown')}):")
                    answer_parts.append(doc.content[:500] + "..." if len(doc.content) > 500 else doc.content)

                rag_answer = "\n".join(answer_parts)

                return {
                    **state,
                    "messages": [AIMessage(content=rag_answer)],
                    "rag_checked": True,
                    "rag_can_answer": True,
                    "rag_answer": rag_answer,
                    "rag_similarity": best_similarity,
                    "final_answer": rag_answer,
                    "next_agent": "FINISH",  # Skip SQL/Genie entirely
                    "iterations": iterations + 1
                }

            else:
                # Mode 2: Context Enrichment - Provide hints to schema/query
                logger.info(f"✓ RAG providing context hints (similarity: {best_similarity:.3f})")

                # Build context from top documents
                context_parts = ["**RAG Context (from documentation):**\n"]
                for i, doc in enumerate(results):
                    context_parts.append(f"- {doc.content[:200]}...")

                rag_context = "\n".join(context_parts)

                return {
                    **state,
                    "rag_checked": True,
                    "rag_can_answer": False,
                    "rag_context": rag_context,
                    "rag_similarity": best_similarity,
                    "next_agent": "schema",  # Proceed to schema with context
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return {
                **state,
                "rag_checked": True,
                "rag_can_answer": False,
                "next_agent": "schema",
                "iterations": iterations + 1
            }

    return rag_node


# ============================================================================
# SUPERVISOR / ROUTER
# ============================================================================

def create_supervisor_node(llm: AzureChatOpenAI):
    """
    Simple supervisor that routes based on state.

    Routing logic:
    1. If no schema analysis yet → schema
    2. If not answerable → human
    3. If answerable but no query plan → query_planner
    4. If query plan exists but no genie results → genie
    5. If genie results exist → synthesis
    6. If iterations >= 5 → synthesis (force end)
    """

    def supervisor_node(state: AgentState) -> Dict[str, Any]:
        logger.info("=== Supervisor ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get state tracking fields
        rag_checked = state.get("rag_checked", False)
        rag_can_answer = state.get("rag_can_answer", False)
        schema_analyzed = state.get("schema_analyzed", False)
        query_planned = state.get("query_planned", False)
        genie_executed = state.get("genie_executed", False)
        is_answerable = state.get("is_answerable", False)
        needs_clarification = state.get("needs_clarification", False)

        logger.info(f"Iteration {iterations}")
        logger.info(f"State: rag_checked={rag_checked}, rag_can_answer={rag_can_answer}, "
                   f"schema_analyzed={schema_analyzed}, query_planned={query_planned}, "
                   f"genie_executed={genie_executed}, is_answerable={is_answerable}, "
                   f"needs_clarification={needs_clarification}")

        # Safety: Force synthesis after 10 iterations
        if iterations >= 10:
            logger.warning("Max iterations reached - forcing synthesis")
            return {**state, "next_agent": "synthesis"}

        # Check RAG first (if enabled and not checked)
        if config.rag.enabled and not rag_checked:
            logger.info("→ Routing to: rag (RAG enabled, not checked yet)")
            return {**state, "next_agent": "rag"}

        # If RAG answered standalone, go to synthesis
        if rag_can_answer:
            logger.info("→ Routing to: synthesis (RAG answered standalone)")
            return {**state, "next_agent": "synthesis"}

        # Check if user just provided clarification
        if len(messages) >= 2:
            last_msg = messages[-1]
            second_last = messages[-2]
            if (isinstance(second_last, AIMessage) and
                "clarification" in second_last.content.lower() and
                isinstance(last_msg, HumanMessage)):

                # User responded to clarification
                user_response = last_msg.content.lower()
                if any(phrase in user_response for phrase in ["just proceed", "use default", "proceed", "go ahead", "continue anyway", "assume"]):
                    logger.info("✓ User wants defaults - going to query planner")
                    return {**state, "next_agent": "query_planner", "is_answerable": True, "needs_clarification": False}
                else:
                    logger.info("✓ User provided clarification - re-analyzing schema")
                    return {**state, "next_agent": "schema", "schema_analyzed": False, "needs_clarification": False, "clarification_provided": True}

        # Routing logic based on explicit state fields
        if not schema_analyzed:
            logger.info("→ Routing to: schema (not analyzed yet)")
            return {**state, "next_agent": "schema"}

        if needs_clarification:
            logger.info("→ Routing to: human (needs clarification)")
            return {**state, "next_agent": "human"}

        if not is_answerable:
            logger.info("→ Routing to: synthesis (not answerable)")
            return {**state, "next_agent": "synthesis"}

        if is_answerable and not query_planned:
            logger.info("→ Routing to: query_planner (answerable, need plan)")
            return {**state, "next_agent": "query_planner"}

        if query_planned and not genie_executed:
            logger.info("→ Routing to: genie (have plan, need execution)")
            return {**state, "next_agent": "genie"}

        if genie_executed:
            logger.info("→ Routing to: synthesis (have results)")
            return {**state, "next_agent": "synthesis"}

        # Default: go to synthesis
        logger.info("→ Routing to: synthesis (default)")
        return {**state, "next_agent": "synthesis"}

    return supervisor_node


def route_from_supervisor(state: AgentState) -> str:
    """Route based on supervisor decision"""
    next_agent = state.get("next_agent", "FINISH")
    logger.info(f"Routing to: {next_agent}")
    return next_agent


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_multi_agent_graph():
    """Build the simplified multi-agent graph"""
    logger.info("Initializing simplified multi-agent system...")

    # Initialize LLM
    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        temperature=0.3,
    )

    # Initialize Databricks client
    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    # Initialize schema reader
    schema_reader = UnitySchemaReader(workspace_client)

    # Initialize embedding service (for RAG and caching)
    embedding_service = None
    rag_store = None
    sql_cache = None

    try:
        embedding_service = initialize_embedding_service(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            api_version=config.azure_openai.api_version,
            deployment_name=config.azure_openai.embedding_deployment,
            cache_enabled=True
        )
        logger.info("✓ Embedding service initialized")

        # Initialize RAG store (if enabled)
        if config.rag.enabled:
            rag_store = initialize_rag_store(
                embedding_service=embedding_service,
                vector_store_path=config.rag.vector_store_path,
                chunk_size=config.rag.chunk_size,
                chunk_overlap=config.rag.chunk_overlap
            )

            # Load documents if directory exists and has files
            import os
            if os.path.exists(config.rag.documents_path) and os.listdir(config.rag.documents_path):
                try:
                    documents = load_documents_from_directory(config.rag.documents_path)
                    if documents:
                        rag_store.add_documents(documents)
                        logger.info(f"✓ RAG initialized with {len(documents)} documents")
                    else:
                        logger.info("RAG enabled but no documents found")
                except Exception as e:
                    logger.warning(f"Failed to load RAG documents: {e}")
            else:
                logger.info("RAG enabled but no documents directory found")

        # Initialize SQL cache (if enabled)
        if config.cache.enabled:
            sql_cache = initialize_sql_cache(
                embedding_service=embedding_service,
                ttl_seconds=config.cache.ttl_seconds,
                similarity_threshold=config.cache.similarity_threshold,
                max_entries=config.cache.max_entries
            )
            logger.info("✓ Smart SQL cache initialized")

    except Exception as e:
        logger.warning(f"RAG/Cache initialization failed (continuing without): {e}")

    # Create agents
    supervisor_node = create_supervisor_node(llm)
    schema_node = create_schema_analysis_agent(schema_reader, llm)
    query_planner_node = create_query_planner_agent(llm)
    genie_node = create_genie_executor_node(workspace_client, sql_cache=sql_cache)
    synthesis_node = create_synthesis_agent(llm)
    human_node = create_human_node()

    # Create RAG node (if enabled)
    rag_node = None
    if config.rag.enabled and rag_store:
        rag_node = create_rag_node(rag_store, config)
        logger.info("✓ RAG node created")

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("schema", schema_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("genie", genie_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("human", human_node)

    # Add RAG node (if enabled)
    if rag_node:
        workflow.add_node("rag", rag_node)

    # Entry point
    workflow.set_entry_point("supervisor")

    # Supervisor routes to agents
    routing_dict = {
        "schema": "schema",
        "query_planner": "query_planner",
        "genie": "genie",
        "synthesis": "synthesis",
        "human": "human",
        "FINISH": END
    }

    # Add RAG to routing (if enabled)
    if rag_node:
        routing_dict["rag"] = "rag"

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        routing_dict
    )

    # All agents loop back to supervisor (except synthesis which ends)
    workflow.add_edge("schema", "supervisor")
    workflow.add_edge("query_planner", "supervisor")
    workflow.add_edge("genie", "supervisor")
    workflow.add_edge("synthesis", END)
    workflow.add_edge("human", "supervisor")  # Human loops back to supervisor!

    # RAG loops back to supervisor (if enabled)
    if rag_node:
        workflow.add_edge("rag", "supervisor")

    # Compile with memory
    # Note: Recursion is limited by supervisor's iteration counter (max 10)
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    logger.info("✓ Simplified multi-agent system initialized")

    return graph


# ============================================================================
# PUBLIC API
# ============================================================================

def get_agent():
    """Get the compiled multi-agent graph"""
    return create_multi_agent_graph()
