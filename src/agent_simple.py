"""
Simplified Multi-Agent System - Clean Architecture
=================================================

A streamlined multi-agent orchestrator that:
1. Reads Unity Catalog schemas
2. Analyzes questions for answerability
3. Plans and formats clean queries
4. Executes via Genie
5. Synthesizes results

NO validation loops - trust the results!

Author: Claude Code
Version: 5.0.0-simple
Date: 2026-02-11
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

logger = get_logger(__name__)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class AgentState(TypedDict):
    """State passed between agents"""
    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str
    iterations: int
    final_answer: str
    schema_info: str
    is_answerable: bool
    formatted_query: str


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

        # Get user question (last human message)
        user_question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break

        if not user_question:
            logger.error("No user question found")
            return {
                "next_agent": "human",
                "is_answerable": False,
                "iterations": iterations + 1
            }

        # Read schemas if not already in state
        schema_info = state.get("schema_info", "")
        if not schema_info:
            logger.info("Reading Unity Catalog schemas...")
            schema_info = schema_reader.read_all_configured_schemas()
            logger.info(f"✓ Loaded schemas for {len(config.databricks.unity_tables)} tables")

        # Analyze with LLM using semantic understanding
        analysis_prompt = f"""You are a data analyst expert analyzing Unity Catalog schemas.

Your task is to understand the USER'S INTENT and match it to available data using SEMANTIC UNDERSTANDING.

CRITICAL: DO NOT make assumptions about data availability! Only look at the schema metadata provided.
- If user mentions October 2025 and you don't see date range info in schema → ASK for clarification
- DO NOT say "data only available up to October 2023" unless schema explicitly says so
- The schema shows column STRUCTURE, not data CONTENTS

INSTRUCTIONS:

1. READ THE COLUMN DESCRIPTIONS CAREFULLY
   - Column names may not directly match user's words
   - The COMMENT/DESCRIPTION tells you what the column actually contains
   - Use your understanding to find semantic matches

2. UNDERSTAND USER INTENT
   When user asks for:
   - "sentiment" → They want emotional/satisfaction data (look for sentiment_score, satisfaction, nps, etc.)
   - "location" or city name → They want geographic data (look for city, location, region, geo columns)
   - "time" or date → They want temporal data (look for date, timestamp, period columns)
   - "revenue" or "sales" → They want financial data (look for amount, revenue, sales columns)

3. BE FLEXIBLE WITH COLUMN NAMES
   Example: If user asks "sentiment for bangalore"
   - Look for ANY column that contains sentiment data (sentiment_score, customer_satisfaction, nps_score, etc.)
   - Look for ANY column that contains location (city, location, geography, region, etc.)
   - The column COMMENT will tell you what the data means

4. DETERMINE ANSWERABILITY
   Question is ANSWERABLE WITHOUT CLARIFICATION if:
   - Exactly ONE table clearly matches the user's intent
   - All necessary filters are specified (date range, location, etc.)
   - The query is complete and unambiguous

   Question NEEDS CLARIFICATION if:
   - MULTIPLE tables have matching data (which one to use?)
   - Missing time period for time-series data
   - Missing important filters (location, category, etc.)
   - Query is too vague or ambiguous

   Question is NOT ANSWERABLE if:
   - No columns exist that could provide the requested information
   - The user's request is impossible with available data

5. OUTPUT FORMAT
   Respond in this EXACT format:

   **ANSWERABLE: YES** (if can answer without clarification)
   **ANSWERABLE: NEEDS_CLARIFICATION** (if answerable but needs more details)
   **ANSWERABLE: NO** (if not answerable with available data)

   **REASONING:**
   [Explain your semantic matching logic and what's missing]

   **MATCHING TABLES AND COLUMNS:**
   [List all tables and columns that match]

   **WHAT'S MISSING:**
   [What details are not specified: table choice, date range, filters, etc.]

   **CLARIFICATION QUESTIONS:**
   [Specific questions to ask the user. If they say "just proceed", we'll use defaults]

AVAILABLE SCHEMAS:
{schema_info}

USER QUESTION:
{user_question}

Now analyze:"""

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
                    "messages": [AIMessage(content=clarification_msg)],
                    "schema_info": schema_info,
                    "is_answerable": False,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

            elif "ANSWERABLE: YES" in content_upper:
                logger.info("✓ Question is answerable with available data")
                return {
                    "messages": [AIMessage(content=f"Schema Analysis:\n{analysis_content}")],
                    "schema_info": schema_info,
                    "is_answerable": True,
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
                    "messages": [AIMessage(content=f"I'm sorry, but {reason}")],
                    "schema_info": schema_info,
                    "is_answerable": False,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"Schema analysis failed: {e}", exc_info=True)
            return {
                "messages": [AIMessage(content=f"Schema analysis error: {str(e)}")],
                "next_agent": "human",
                "is_answerable": False,
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

        planning_prompt = f"""You are a query planning specialist for Databricks Genie.

Your task is to create NATURAL, CONVERSATIONAL queries that Genie can understand.

IMPORTANT RULES:
1. Format queries as NATURAL QUESTIONS (not SQL!)
2. Be specific about table names, filters, and what you want
3. If user said "just proceed" or provided defaults, make reasonable assumptions

GOOD NATURAL QUERIES:
- "Show me sentiment data for bangalore from the pc_sales table"
- "What is the average revenue for orders in October 2025?"
- "From the PES table, show negative sentiment entries for bangalore in October 2025"

BAD QUERIES:
- "From catalog.schema.sales, show sentiment_score, city where city = 'bangalore'" (too SQL-like)
- "Can you show me sentiment data?" (too vague - missing table/filters)

{"USER WANTS DEFAULTS:" if use_defaults else ""}
{f"The user said '{latest_user_input}' - make reasonable assumptions for missing details" if use_defaults else ""}

AVAILABLE TABLES:
{schema_info}

USER CONTEXT:
{user_context}

SCHEMA ANALYSIS:
{schema_analysis}

Now create natural, conversational queries for Genie. If multiple tables are involved, create separate queries.
Output in this format:

**QUERY 1:**
[Natural question for Genie]

**QUERY 2:**
[Natural question if needed]

If user requested defaults, choose the most relevant table and reasonable date ranges (e.g., last 3 months).
"""

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
                "messages": [AIMessage(content=f"Query Plan:\n{query_plan}")],
                "formatted_query": formatted_query_text,
                "next_agent": "genie",
                "iterations": iterations + 1
            }

        except Exception as e:
            logger.error(f"Query planning failed: {e}", exc_info=True)
            return {
                "messages": [AIMessage(content=f"Query planning error: {str(e)}")],
                "next_agent": "synthesis",
                "iterations": iterations + 1
            }

    return query_planner_node


def create_genie_executor_node(workspace_client: WorkspaceClient):
    """
    Agent that:
    1. Takes formatted queries
    2. Executes them via Genie
    3. Returns results
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
                "messages": [AIMessage(content="Error: No query to execute")],
                "next_agent": "synthesis",
                "iterations": iterations + 1
            }

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

        return {
            "messages": [AIMessage(content=f"Genie Results:\n\n{combined_results}")],
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
                "messages": [AIMessage(content=final_answer)],
                "final_answer": final_answer,
                "next_agent": "FINISH",
                "iterations": iterations + 1
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            return {
                "messages": [AIMessage(content=f"I encountered an error while synthesizing results: {str(e)}")],
                "final_answer": f"Error: {str(e)}",
                "next_agent": "FINISH",
                "iterations": iterations + 1
            }

    return synthesis_node


def create_human_node():
    """
    Agent that handles human clarification requests.
    In production, replace with actual human-in-loop system.
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

        # In CLI mode, this will return and wait for user input
        # The user's response will come as a new message in the next invoke call

        return {
            "messages": [AIMessage(content=clarification_question)],
            "final_answer": clarification_question,
            "next_agent": "FINISH",  # End and wait for user response
            "iterations": iterations + 1
        }

    return human_node


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
        is_answerable = state.get("is_answerable", None)
        formatted_query = state.get("formatted_query", "")

        logger.info(f"Iteration {iterations}")

        # Safety: Force synthesis after 5 iterations
        if iterations >= 5:
            logger.warning("Max iterations reached - forcing synthesis")
            return {"next_agent": "synthesis"}

        # Check if we just received a clarification (user responded to human node)
        received_clarification = False
        user_wants_defaults = False

        if len(messages) >= 2:
            last_msg = messages[-1]
            second_last = messages[-2]
            if (isinstance(second_last, AIMessage) and
                "clarification" in second_last.content.lower() and
                isinstance(last_msg, HumanMessage)):
                received_clarification = True

                # Check if user said "just proceed" or similar
                user_response = last_msg.content.lower()
                if any(phrase in user_response for phrase in ["just proceed", "use default", "proceed", "go ahead", "continue anyway", "assume"]):
                    user_wants_defaults = True
                    logger.info("✓ User wants to proceed with defaults - going to query planner")
                    # User wants defaults - go straight to query planner with current schema
                    return {"next_agent": "query_planner", "is_answerable": True}
                else:
                    logger.info("✓ Received clarification details from user - re-analyzing")
                    # User provided actual details - re-analyze with new info
                    return {"next_agent": "schema"}

        # Check what's been done
        has_schema_analysis = any(
            "Schema Analysis" in str(msg.content) or "[Schema Analysis Complete" in str(msg.content)
            for msg in messages if isinstance(msg, AIMessage)
        )
        has_query_plan = any("Query Plan" in str(msg.content) for msg in messages if isinstance(msg, AIMessage))
        has_genie_results = any("Genie Results" in str(msg.content) for msg in messages if isinstance(msg, AIMessage))

        # Check if waiting for clarification
        needs_clarification = any(
            "Needs Clarification" in str(msg.content) or "need some clarification" in str(msg.content)
            for msg in messages if isinstance(msg, AIMessage)
        )

        # Routing logic
        if not has_schema_analysis:
            logger.info("→ Routing to: schema (no analysis yet)")
            return {"next_agent": "schema"}

        if needs_clarification and is_answerable == False:
            logger.info("→ Routing to: human (needs clarification)")
            return {"next_agent": "human"}

        if is_answerable == False:
            logger.info("→ Routing to: human (not answerable)")
            return {"next_agent": "human"}

        if is_answerable == True and not has_query_plan:
            logger.info("→ Routing to: query_planner (answerable, need plan)")
            return {"next_agent": "query_planner"}

        if has_query_plan and not has_genie_results:
            logger.info("→ Routing to: genie (have plan, need execution)")
            return {"next_agent": "genie"}

        if has_genie_results:
            logger.info("→ Routing to: synthesis (have results)")
            return {"next_agent": "synthesis"}

        # Default: go to synthesis
        logger.info("→ Routing to: synthesis (default)")
        return {"next_agent": "synthesis"}

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

    # Create agents
    supervisor_node = create_supervisor_node(llm)
    schema_node = create_schema_analysis_agent(schema_reader, llm)
    query_planner_node = create_query_planner_agent(llm)
    genie_node = create_genie_executor_node(workspace_client)
    synthesis_node = create_synthesis_agent(llm)
    human_node = create_human_node()

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("schema", schema_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("genie", genie_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("human", human_node)

    # Entry point
    workflow.set_entry_point("supervisor")

    # Supervisor routes to agents
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "schema": "schema",
            "query_planner": "query_planner",
            "genie": "genie",
            "synthesis": "synthesis",
            "human": "human",
            "FINISH": END
        }
    )

    # All agents loop back to supervisor (except synthesis and human which end)
    workflow.add_edge("schema", "supervisor")
    workflow.add_edge("query_planner", "supervisor")
    workflow.add_edge("genie", "supervisor")
    workflow.add_edge("synthesis", END)
    workflow.add_edge("human", END)

    # Compile with memory
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
