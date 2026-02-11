"""
Enhanced Multi-Agent Architecture v4.0 - CLEAN VERSION
=======================================================

Intelligent multi-agent system with:
- Schema Agent: READS Unity Catalog tables, columns, comments
- Query Planner: Decomposes complex questions
- Clean Genie Execution: Formatted questions only
- Validation: Result checking
- Agentic RAG: Conditional integration

Author: Claude Code
Version: 4.0.0-clean
Date: 2026-02-11
"""

import operator
import json
from typing import Annotated, List, Dict, Any, Optional, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from databricks.sdk import WorkspaceClient
from databricks_langchain import GenieAgent
from langchain_community.vectorstores import FAISS

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_core.tools import create_retriever_tool
except ImportError:
    from langchain.tools.retriever import create_retriever_tool

from src.core.config import config
from src.utils.parsers import load_documents_from_directory
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class AgentState(TypedDict):
    """Enhanced state with schema understanding and planning"""
    messages: Annotated[List[BaseMessage], operator.add]

    # Original question
    original_question: str

    # Schema analysis (from Unity Catalog)
    schema_info: Dict[str, Any]  # Full schema with tables, columns, comments
    relevant_tables: List[str]
    is_answerable: bool
    missing_information: List[str]

    # Query planning
    formatted_queries: List[str]  # Clean questions for Genie
    execution_mode: str  # "genie_only", "rag_only", "genie_and_rag"

    # Results
    genie_results: List[str]
    rag_results: List[str]

    # Validation
    is_complete: bool
    validation_feedback: str

    # Control flow
    next_agent: str
    iterations: int
    final_answer: str


# ============================================================================
# 1. SCHEMA AGENT - READS UNITY CATALOG
# ============================================================================

class UnitySchemaReader:
    """
    Reads Unity Catalog tables, columns, and comments.

    Uses Databricks SDK to:
    - List all tables in configured catalogs/schemas
    - Get column names, types, and comments
    - Get table comments and descriptions
    - Build searchable schema metadata
    """

    def __init__(self, workspace_client: WorkspaceClient):
        """Initialize with Databricks workspace client"""
        self.client = workspace_client
        self.catalog_api = workspace_client.catalogs
        self.schema_api = workspace_client.schemas
        self.table_api = workspace_client.tables
        self.schema_cache = {}

        logger.info("Unity Schema Reader initialized")

    def read_table_schema(self, full_table_name: str) -> Dict[str, Any]:
        """
        Read schema for a specific table from Unity Catalog.

        Args:
            full_table_name: Format "catalog.schema.table"

        Returns:
            Dict with table info, columns, comments
        """
        try:
            # Check cache
            if full_table_name in self.schema_cache:
                logger.info(f"Using cached schema for {full_table_name}")
                return self.schema_cache[full_table_name]

            logger.info(f"Reading schema from Unity Catalog: {full_table_name}")

            # Get table info from Unity Catalog
            table_info = self.table_api.get(full_table_name)

            # Extract schema information
            schema_info = {
                "table_name": full_table_name,
                "table_comment": table_info.comment or "No comment",
                "table_type": table_info.table_type.value if table_info.table_type else "TABLE",
                "columns": []
            }

            # Get columns with types and comments
            if table_info.columns:
                for col in table_info.columns:
                    column_info = {
                        "name": col.name,
                        "type": col.type_name.value if col.type_name else "STRING",
                        "comment": col.comment or "No comment",
                        "nullable": col.nullable if hasattr(col, 'nullable') else True
                    }
                    schema_info["columns"].append(column_info)

            # Cache the result
            self.schema_cache[full_table_name] = schema_info

            logger.info(f"✓ Loaded schema for {full_table_name}: "
                       f"{len(schema_info['columns'])} columns")

            return schema_info

        except Exception as e:
            logger.error(f"Failed to read schema for {full_table_name}: {e}")
            return {
                "table_name": full_table_name,
                "table_comment": f"Error reading schema: {e}",
                "table_type": "UNKNOWN",
                "columns": []
            }

    def read_all_configured_schemas(self) -> Dict[str, Any]:
        """
        Read schemas for all configured Unity Catalog tables.

        Returns:
            Dict mapping table names to their schema info
        """
        all_schemas = {}
        configured_tables = config.databricks.unity_tables

        logger.info(f"Reading schemas for {len(configured_tables)} configured tables")

        for table_name in configured_tables:
            schema_info = self.read_table_schema(table_name)
            all_schemas[table_name] = schema_info

        logger.info(f"✓ Loaded {len(all_schemas)} table schemas")
        return all_schemas


class SchemaAnalysisAgent:
    """
    Analyzes questions against Unity Catalog schema.

    Uses LLM to understand:
    - Which tables are relevant to the question
    - Which columns are needed
    - Whether the question can be answered
    - What information is missing
    """

    def __init__(self, schema_reader: UnitySchemaReader):
        """Initialize with schema reader"""
        self.schema_reader = schema_reader
        self.all_schemas = schema_reader.read_all_configured_schemas()

        self.llm = AzureChatOpenAI(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.gpt4o_deployment,
            api_version=config.azure_openai.api_version,
            temperature=0.0,
        )

        logger.info("Schema Analysis Agent initialized with Unity Catalog metadata")

    def get_schema_summary(self) -> str:
        """Get human-readable schema summary"""
        summary_lines = []
        for table_name, schema in self.all_schemas.items():
            summary_lines.append(f"\nTable: {table_name}")
            summary_lines.append(f"  Description: {schema['table_comment']}")
            summary_lines.append(f"  Columns ({len(schema['columns'])}):")
            for col in schema['columns']:
                summary_lines.append(f"    - {col['name']} ({col['type']}): {col['comment']}")

        return "\n".join(summary_lines)

    def analyze_question(self, question: str) -> Dict[str, Any]:
        """
        Analyze question against Unity Catalog schema.

        Returns:
            Dict with analysis results
        """
        logger.info(f"Analyzing question against Unity Catalog: {question}")

        schema_summary = self.get_schema_summary()

        analysis_prompt = f"""You are a data analyst expert analyzing Unity Catalog schemas.

AVAILABLE TABLES AND SCHEMAS:
{schema_summary}

USER QUESTION:
{question}

Your task is to understand the USER'S INTENT and match it to available data using SEMANTIC UNDERSTANDING.

INSTRUCTIONS:

1. READ THE COLUMN DESCRIPTIONS CAREFULLY
   - Column names may not directly match user's words
   - The COMMENT/DESCRIPTION tells you what the column actually contains
   - Use your understanding to find semantic matches

2. UNDERSTAND USER INTENT
   When user asks for:
   - "sentiment" → They want emotional/satisfaction data (could be ratings, scores, feedback, satisfaction levels)
   - "location" or city name → They want geographic data (could be in outlet, branch, region, city, area columns)
   - "time" or date → They want temporal data (could be in date, month, year, period columns)
   - "sales" → They want transaction/revenue data
   - "performance" → They want metrics/KPIs

3. MATCH SEMANTICALLY, NOT LITERALLY
   Examples:
   - User: "sentiment for bangalore"
     Column: "PCSL1 - satisfaction level" → YES, this IS sentiment data!
     Column: "Outlet" → YES, this can contain bangalore!

   - User: "customer feedback by region"
     Column: "rating_score" → YES, ratings ARE feedback!
     Column: "branch_location" → YES, branch IS a region!

4. BE INTELLIGENT ABOUT MISSING INFO
   - If you found relevant columns but they need filtering (e.g., "which outlet in bangalore?"),
     mark as ANSWERABLE but note what needs clarification
   - Only mark as NOT ANSWERABLE if truly no relevant data exists

5. EXPLAIN YOUR SEMANTIC MATCHING
   In "reasoning", explain which columns match which user concepts and WHY

Respond in JSON format:
{{
    "is_answerable": true/false,
    "relevant_tables": ["table1", "table2"],
    "relevant_columns": {{"table1": ["actual_column_name", "another_column"]}},
    "missing_information": ["only if truly missing - be specific"],
    "needs_sql": true/false,
    "needs_documents": true/false,
    "reasoning": "Explain semantic matches: User asked for X, found it in column Y because Y's description indicates..."
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a schema analysis expert. Always respond with valid JSON."),
                HumanMessage(content=analysis_prompt)
            ])

            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            logger.info(f"Schema analysis: answerable={result['is_answerable']}, "
                       f"tables={result['relevant_tables']}")

            return result

        except Exception as e:
            logger.error(f"Schema analysis failed: {e}")
            return {
                "is_answerable": False,
                "relevant_tables": [],
                "relevant_columns": {},
                "missing_information": [f"Analysis error: {e}"],
                "needs_sql": False,
                "needs_documents": False,
                "reasoning": f"Error: {e}"
            }


def create_schema_node(schema_agent: SchemaAnalysisAgent):
    """Create schema analysis node"""

    def schema_node(state: AgentState) -> Dict[str, Any]:
        """Analyze question against Unity Catalog"""

        messages = state["messages"]
        user_messages = [msg.content for msg in messages if isinstance(msg, HumanMessage)]
        full_question = " ".join(user_messages)

        # Analyze against Unity Catalog schema
        analysis = schema_agent.analyze_question(full_question)

        # Determine execution mode
        if analysis["needs_sql"] and analysis["needs_documents"]:
            execution_mode = "genie_and_rag"
        elif analysis["needs_sql"]:
            execution_mode = "genie_only"
        elif analysis["needs_documents"]:
            execution_mode = "rag_only"
        else:
            execution_mode = "genie_only"  # Default

        return {
            "original_question": full_question,
            "schema_info": schema_agent.all_schemas,
            "relevant_tables": analysis["relevant_tables"],
            "is_answerable": analysis["is_answerable"],
            "missing_information": analysis["missing_information"],
            "execution_mode": execution_mode,
            "messages": [AIMessage(content=f"Schema Analysis:\n{analysis['reasoning']}")]
        }

    return schema_node


# ============================================================================
# 2. QUERY PLANNER - CLEAN QUESTION FORMATTING
# ============================================================================

def create_query_planner_node():
    """Create query planner node"""

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.2,
    )

    def query_planner_node(state: AgentState) -> Dict[str, Any]:
        """Plan and format clean queries"""

        question = state["original_question"]
        relevant_tables = state["relevant_tables"]
        schema_info = state["schema_info"]

        # Build column info for relevant tables
        column_info = {}
        for table in relevant_tables:
            if table in schema_info:
                column_info[table] = [
                    f"{col['name']} ({col['type']}): {col['comment']}"
                    for col in schema_info[table]["columns"]
                ]

        planning_prompt = f"""You are a SQL query planner expert.

QUESTION:
{question}

RELEVANT TABLES:
{relevant_tables}

COLUMNS AVAILABLE:
{json.dumps(column_info, indent=2)}

Create CLEAN, SPECIFIC queries for a SQL agent (Databricks Genie).

IMPORTANT:
- Format as: "From [table], show [specific columns] where [conditions]"
- Be explicit about what to retrieve
- Include necessary filters (date, location, etc.) if mentioned in question
- If question is complex, break into 2-3 sub-queries

Respond in JSON:
{{
    "queries": [
        "From table1, show column1, column2 where condition",
        "From table2, show column3 where condition"
    ],
    "reasoning": "why these queries"
}}"""

        try:
            response = llm.invoke([
                SystemMessage(content="You are a query planning expert. Always respond with valid JSON."),
                HumanMessage(content=planning_prompt)
            ])

            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            formatted_queries = result.get("queries", [])

            logger.info(f"Query plan: {len(formatted_queries)} queries")

            return {
                "formatted_queries": formatted_queries,
                "messages": [AIMessage(content=f"Query Plan:\n{result['reasoning']}")]
            }

        except Exception as e:
            logger.error(f"Query planning failed: {e}")
            # Fallback: simple query
            simple_query = f"From {', '.join(relevant_tables)}, answer: {question}"
            return {
                "formatted_queries": [simple_query],
                "messages": [AIMessage(content=f"Using simple query due to error: {e}")]
            }

    return query_planner_node


# ============================================================================
# 3. GENIE EXECUTOR - CLEAN QUERIES
# ============================================================================

def create_genie_executor():
    """Create Genie executor with clean queries"""

    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    genie_agent = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="SQL_Specialist",
        description="Execute clean SQL queries on Unity Catalog",
        client=workspace_client,
        return_pandas=False,
    )

    def genie_executor_node(state: AgentState) -> Dict[str, Any]:
        """Execute formatted queries via Genie"""

        formatted_queries = state["formatted_queries"]
        results = []

        logger.info(f"Executing {len(formatted_queries)} queries via Genie")

        for idx, query in enumerate(formatted_queries):
            try:
                logger.info(f"Genie Query {idx+1}: {query}")

                # Execute CLEAN query (not chat history!)
                result = genie_agent.invoke({"question": query})
                result_text = result if isinstance(result, str) else str(result)
                results.append(result_text)

                logger.info(f"✓ Genie Query {idx+1} completed")

            except Exception as e:
                logger.error(f"Genie query {idx+1} failed: {e}")
                results.append(f"Query failed: {e}")

        combined_result = "\n\n".join([
            f"Query {i+1} Result:\n{r}"
            for i, r in enumerate(results)
        ])

        return {
            "genie_results": results,
            "messages": [AIMessage(content=f"SQL Results:\n{combined_result}")]
        }

    return genie_executor_node


# ============================================================================
# 4. RAG AGENT
# ============================================================================

def create_rag_agent():
    """Create RAG agent for documents"""
    try:
        docs = load_documents_from_directory("./data/documents")

        if not docs:
            logger.warning("No documents found - RAG not available")
            return None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)

        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.embedding_deployment,
            api_version=config.azure_openai.api_version,
        )

        import os
        faiss_path = "./data/faiss_rag_index"

        if os.path.exists(f"{faiss_path}/index.faiss"):
            vectorstore = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
        else:
            vectorstore = FAISS.from_documents(splits, embeddings)
            os.makedirs(faiss_path, exist_ok=True)
            vectorstore.save_local(faiss_path)

        rag_tool = create_retriever_tool(
            vectorstore.as_retriever(search_kwargs={"k": 5}),
            "document_search",
            "Search documents"
        )

        logger.info("RAG Agent created")
        return rag_tool

    except Exception as e:
        logger.error(f"RAG creation failed: {e}")
        return None


def create_rag_executor_node(rag_tool):
    """Create RAG executor node"""
    if rag_tool is None:
        return None

    def rag_executor_node(state: AgentState) -> Dict[str, Any]:
        question = state["original_question"]

        try:
            result = rag_tool.invoke({"query": question})
            return {
                "rag_results": [result],
                "messages": [AIMessage(content=f"Document Context:\n{result}")]
            }
        except Exception as e:
            logger.error(f"RAG failed: {e}")
            return {
                "rag_results": [],
                "messages": [AIMessage(content=f"RAG failed: {e}")]
            }

    return rag_executor_node


# ============================================================================
# 5. VALIDATION AGENT
# ============================================================================

def create_validation_node():
    """Create validation node"""

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.0,
    )

    def validation_node(state: AgentState) -> Dict[str, Any]:
        """Validate results"""

        question = state["original_question"]
        genie_results = state.get("genie_results", [])
        rag_results = state.get("rag_results", [])

        all_results = "\n".join(genie_results) + "\n" + "\n".join(rag_results)

        validation_prompt = f"""Did these results answer the question?

QUESTION: {question}

RESULTS: {all_results}

Respond JSON:
{{
    "is_complete": true/false,
    "feedback": "explanation",
    "next_action": "synthesis" or "human" or "replan"
}}"""

        try:
            response = llm.invoke([
                SystemMessage(content="You are a validator. Always respond with valid JSON."),
                HumanMessage(content=validation_prompt)
            ])

            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            return {
                "is_complete": result["is_complete"],
                "validation_feedback": result["feedback"],
                "next_agent": result["next_action"],
                "messages": [AIMessage(content=f"Validation: {result['feedback']}")]
            }

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "is_complete": False,
                "validation_feedback": f"Error: {e}",
                "next_agent": "synthesis"
            }

    return validation_node


# ============================================================================
# 6. SUPERVISOR
# ============================================================================

def create_supervisor():
    """Create supervisor"""

    def supervisor_node(state: AgentState) -> Dict[str, Any]:
        """Route to next agent"""

        iterations = state.get("iterations", 0)

        if iterations >= 5:
            return {"next_agent": "human", "iterations": iterations + 1}

        messages = state["messages"]

        # Check if we just received clarification after asking human
        # (last 2 messages: clarification request from us, then user response)
        received_clarification = False
        if len(messages) >= 2:
            last_msg = messages[-1]
            second_last = messages[-2]
            # If second-to-last was our clarification request and last is user's response
            if (isinstance(second_last, AIMessage) and
                "needs more details" in second_last.content and
                isinstance(last_msg, HumanMessage)):
                received_clarification = True

        # Routing logic
        if "Schema Analysis" not in str(messages):
            # First time - analyze schema
            next_agent = "schema"
        elif received_clarification:
            # User provided clarification - re-analyze with full context
            logger.info("Received clarification - re-analyzing with full context")
            next_agent = "schema"
            # Reset analysis flags so we can re-evaluate
            state["is_answerable"] = None  # Will be set by schema agent
            state["missing_information"] = []
        # Check if question is answerable after schema analysis
        elif "Schema Analysis" in str(messages) and not state.get("is_answerable"):
            # Question not answerable - need clarification
            next_agent = "human"
        elif "Query Plan" not in str(messages):
            next_agent = "query_planner"
        elif state.get("formatted_queries") and not state.get("genie_results"):
            execution_mode = state.get("execution_mode", "genie_only")
            if execution_mode == "genie_only":
                next_agent = "genie_executor"
            elif execution_mode == "rag_only":
                next_agent = "rag_executor"
            else:
                next_agent = "genie_executor"  # Execute SQL first
        elif state.get("genie_results") and not state.get("is_complete"):
            next_agent = "validation"
        elif state.get("is_complete"):
            next_agent = state.get("next_agent", "synthesis")
        else:
            next_agent = "synthesis"

        logger.info(f"Supervisor routing to: {next_agent} (iteration {iterations})")

        # Build return dict
        result = {
            "next_agent": next_agent,
            "iterations": iterations + 1
        }

        # If re-analyzing after clarification, reset flags
        if received_clarification and next_agent == "schema":
            result["is_answerable"] = True  # Reset to neutral (schema will set properly)
            result["missing_information"] = []

        return result

    return supervisor_node


# ============================================================================
# 7. SYNTHESIS & HUMAN
# ============================================================================

def create_synthesis_node():
    """Create synthesis node"""

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.3,
    )

    def synthesis_node(state: AgentState) -> Dict[str, Any]:
        question = state["original_question"]
        genie_results = state.get("genie_results", [])
        rag_results = state.get("rag_results", [])

        synthesis_prompt = f"""Create a comprehensive answer.

QUESTION: {question}

SQL DATA: {chr(10).join(genie_results) if genie_results else "None"}

DOCUMENTS: {chr(10).join(rag_results) if rag_results else "None"}

Provide a clear, well-formatted answer."""

        response = llm.invoke([
            SystemMessage(content="You are a synthesis expert."),
            HumanMessage(content=synthesis_prompt)
        ])

        return {
            "final_answer": response.content,
            "next_agent": "FINISH",
            "messages": [response]
        }

    return synthesis_node


def create_human_node():
    """Create human clarification node"""

    def human_node(state: AgentState) -> Dict[str, Any]:
        missing_info = state.get("missing_information", [])
        original_question = state.get("original_question", "your question")

        if missing_info:
            clarification = f"""Your question "{original_question}" needs more details.

Please clarify:
{chr(10).join(f"  {i+1}. {item}" for i, item in enumerate(missing_info))}

Once you provide these details, I can query the data and give you an accurate answer."""
        else:
            clarification = "Your question needs more information. Please provide additional details such as:\n  1. Which data source or table?\n  2. What time period?\n  3. Any specific filters (location, category, etc.)?"

        return {
            "final_answer": clarification,
            "next_agent": "FINISH",
            "messages": [AIMessage(content=clarification)]
        }

    return human_node


# ============================================================================
# 8. BUILD GRAPH
# ============================================================================

def create_enhanced_agent():
    """Build enhanced multi-agent graph"""

    logger.info("Building enhanced multi-agent graph v4.0-clean")

    # Initialize Databricks client
    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    # Create schema reader and analyzer
    schema_reader = UnitySchemaReader(workspace_client)
    schema_agent = SchemaAnalysisAgent(schema_reader)

    # Create nodes
    schema_node = create_schema_node(schema_agent)
    query_planner_node = create_query_planner_node()
    genie_executor_node = create_genie_executor()
    rag_tool = create_rag_agent()
    rag_executor_node = create_rag_executor_node(rag_tool) if rag_tool else None
    validation_node = create_validation_node()
    supervisor_node = create_supervisor()
    synthesis_node = create_synthesis_node()
    human_node = create_human_node()

    # Build workflow
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("schema", schema_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("genie_executor", genie_executor_node)
    if rag_executor_node:
        workflow.add_node("rag_executor", rag_executor_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("human", human_node)

    workflow.set_entry_point("supervisor")

    # Routing
    def route_from_supervisor(state: AgentState) -> str:
        next_agent = state.get("next_agent", "schema")
        if next_agent == "FINISH":
            return "synthesis"
        return next_agent

    routing_options = {
        "schema": "schema",
        "query_planner": "query_planner",
        "genie_executor": "genie_executor",
        "validation": "validation",
        "synthesis": "synthesis",
        "human": "human",
    }
    if rag_executor_node:
        routing_options["rag_executor"] = "rag_executor"

    workflow.add_conditional_edges("supervisor", route_from_supervisor, routing_options)

    # Loop back to supervisor
    workflow.add_edge("schema", "supervisor")
    workflow.add_edge("query_planner", "supervisor")
    workflow.add_edge("genie_executor", "supervisor")
    if rag_executor_node:
        workflow.add_edge("rag_executor", "supervisor")
    workflow.add_edge("validation", "supervisor")

    # Terminal nodes
    workflow.add_edge("synthesis", END)
    workflow.add_edge("human", END)

    # Compile
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    logger.info("✅ Enhanced multi-agent graph v4.0-clean created")

    return graph


def get_agent():
    """Get compiled agent"""
    return create_enhanced_agent()


if __name__ == "__main__":
    agent = get_agent()
    print("✅ Enhanced Multi-Agent System v4.0-clean initialized")
