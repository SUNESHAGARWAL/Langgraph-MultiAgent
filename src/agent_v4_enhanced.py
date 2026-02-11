"""
Enhanced Multi-Agent Architecture v4.0
=====================================

Complete intelligent multi-agent system with:
- Schema understanding of Unity Catalog
- Query planning and decomposition
- Clean Genie execution
- Result validation
- Agentic RAG integration
- Human-in-loop for ambiguity

Architecture:
    User Question
        ↓
    Supervisor (Intent Analysis)
        ↓
    Schema Agent (Table Understanding)
        ↓
    Query Planner (Decomposition)
        ↓
    Execution Layer (Genie + RAG conditionally)
        ↓
    Validation Agent (Result Check)
        ↓
    Synthesis (Final Answer)

Author: Claude Code
Version: 4.0.0
Date: 2026-02-11
"""

import operator
import hashlib
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
from src.utils.logging import logger


# ============================================================================
# STATE DEFINITION
# ============================================================================

class EnhancedAgentState(TypedDict):
    """Enhanced state with schema understanding and planning"""
    messages: Annotated[List[BaseMessage], operator.add]

    # Original question tracking
    original_question: str

    # Schema analysis
    relevant_tables: List[str]
    relevant_columns: Dict[str, List[str]]
    schema_confidence: float
    is_answerable: bool
    missing_information: List[str]

    # Query planning
    query_plan: List[Dict[str, Any]]
    needs_decomposition: bool
    formatted_queries: List[str]

    # Execution routing
    needs_sql: bool
    needs_rag: bool
    execution_mode: str  # "genie_only", "rag_only", "genie_and_rag"

    # Results
    genie_results: List[str]
    rag_results: List[str]

    # Validation
    validation_status: str  # "complete", "incomplete", "needs_clarification"
    validation_feedback: str

    # Control flow
    next_agent: str
    iterations: int
    final_answer: str


# ============================================================================
# 1. SCHEMA AGENT - Unity Catalog Understanding
# ============================================================================

class SchemaAgent:
    """
    Understands Unity Catalog schema and determines question answerability.

    Features:
    - Extracts table and column metadata from Unity Catalog
    - Semantic search for relevant tables/columns
    - Determines if question can be answered
    - Identifies missing information
    """

    def __init__(self):
        """Initialize schema agent with Unity Catalog metadata"""
        self.llm = AzureChatOpenAI(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.gpt4o_deployment,
            api_version=config.azure_openai.api_version,
            temperature=0.0,  # Deterministic for schema analysis
        )

        # Load schema metadata
        self.schema_metadata = self._load_schema_metadata()

        logger.info("Schema Agent initialized with Unity Catalog metadata")

    def _load_schema_metadata(self) -> Dict[str, Any]:
        """
        Load Unity Catalog schema metadata.

        In production, this would query Unity Catalog API.
        For now, we use configured table names and infer schema.
        """
        # Get configured tables
        tables = config.databricks.unity_tables

        # Build metadata structure
        metadata = {
            "tables": {},
            "table_descriptions": {}
        }

        for table in tables:
            # Store table info
            metadata["tables"][table] = {
                "name": table,
                "columns": [],  # Will be populated from Unity Catalog
                "description": f"Unity Catalog table: {table}"
            }

            # Create searchable description
            metadata["table_descriptions"][table] = {
                "keywords": self._extract_keywords(table),
                "full_name": table
            }

        logger.info(f"Loaded metadata for {len(tables)} tables")
        return metadata

    def _extract_keywords(self, table_name: str) -> List[str]:
        """Extract searchable keywords from table name"""
        # Split by common separators
        parts = table_name.replace("_", " ").replace("-", " ").split(".")
        keywords = []
        for part in parts:
            keywords.extend(part.lower().split())
        return keywords

    def analyze_question(self, question: str) -> Dict[str, Any]:
        """
        Analyze question against schema to determine answerability.

        Returns:
            Dict with:
                - is_answerable: bool
                - relevant_tables: List[str]
                - relevant_columns: Dict[str, List[str]]
                - confidence: float
                - missing_info: List[str]
        """
        logger.info(f"Schema Agent analyzing: {question}")

        # Use LLM to analyze question against schema
        analysis_prompt = f"""You are a database schema expert analyzing Unity Catalog.

AVAILABLE TABLES:
{json.dumps(list(self.schema_metadata['tables'].keys()), indent=2)}

USER QUESTION:
{question}

Analyze this question and determine:
1. Can this question be answered with the available tables?
2. Which tables are relevant?
3. What columns would be needed? (infer from question)
4. What information is missing (if any)?
5. Confidence level (0.0 to 1.0)

Respond in JSON format:
{{
    "is_answerable": true/false,
    "relevant_tables": ["table1", "table2"],
    "inferred_columns": {{"table1": ["col1", "col2"]}},
    "confidence": 0.0-1.0,
    "missing_information": ["detail1", "detail2"] or [],
    "reasoning": "explanation"
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a database schema analyst. Always respond with valid JSON."),
                HumanMessage(content=analysis_prompt)
            ])

            # Parse JSON response
            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            logger.info(f"Schema analysis complete: answerable={result['is_answerable']}, "
                       f"confidence={result['confidence']}")

            return {
                "is_answerable": result.get("is_answerable", False),
                "relevant_tables": result.get("relevant_tables", []),
                "relevant_columns": result.get("inferred_columns", {}),
                "confidence": result.get("confidence", 0.0),
                "missing_info": result.get("missing_information", []),
                "reasoning": result.get("reasoning", "")
            }

        except Exception as e:
            logger.error(f"Schema analysis error: {e}")
            return {
                "is_answerable": False,
                "relevant_tables": [],
                "relevant_columns": {},
                "confidence": 0.0,
                "missing_info": ["Error analyzing schema"],
                "reasoning": str(e)
            }


def create_schema_node(schema_agent: SchemaAgent):
    """Create LangGraph node for schema analysis"""

    def schema_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze question against Unity Catalog schema"""

        # Get original question
        messages = state["messages"]

        # Combine all user messages to understand full context
        user_messages = [msg.content for msg in messages if isinstance(msg, HumanMessage)]
        full_question = " ".join(user_messages)

        # Analyze against schema
        analysis = schema_agent.analyze_question(full_question)

        # Determine if we need SQL vs RAG vs both
        needs_sql = analysis["is_answerable"] and len(analysis["relevant_tables"]) > 0

        # Update state
        return {
            "original_question": full_question,
            "relevant_tables": analysis["relevant_tables"],
            "relevant_columns": analysis["relevant_columns"],
            "schema_confidence": analysis["confidence"],
            "is_answerable": analysis["is_answerable"],
            "missing_information": analysis["missing_info"],
            "needs_sql": needs_sql,
            "messages": [AIMessage(content=f"Schema Analysis: {analysis['reasoning']}")]
        }

    return schema_node


# ============================================================================
# 2. QUERY PLANNER AGENT - Decomposition and Formatting
# ============================================================================

class QueryPlannerAgent:
    """
    Plans query execution and formats clean questions for Genie.

    Features:
    - Detects complex multi-step questions
    - Decomposes into sub-queries
    - Formats clean, specific questions for Genie (NOT chat history)
    - Determines if RAG context is needed
    """

    def __init__(self):
        """Initialize query planner"""
        self.llm = AzureChatOpenAI(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.gpt4o_deployment,
            api_version=config.azure_openai.api_version,
            temperature=0.2,
        )
        logger.info("Query Planner Agent initialized")

    def plan_queries(self,
                    question: str,
                    relevant_tables: List[str],
                    relevant_columns: Dict[str, List[str]],
                    needs_rag: bool = False) -> Dict[str, Any]:
        """
        Plan query execution strategy.

        Returns:
            Dict with:
                - needs_decomposition: bool
                - query_plan: List[Dict] with each sub-query
                - formatted_queries: List[str] clean questions for Genie
                - execution_mode: "genie_only", "rag_only", "genie_and_rag"
        """
        logger.info(f"Planning queries for: {question}")

        planning_prompt = f"""You are a query planning expert for SQL databases.

QUESTION:
{question}

AVAILABLE TABLES:
{', '.join(relevant_tables)}

AVAILABLE COLUMNS:
{json.dumps(relevant_columns, indent=2)}

RAG AVAILABLE: {needs_rag}

Your task:
1. Determine if this is a SIMPLE or COMPLEX question
2. If COMPLEX, break down into sequential sub-queries
3. Format each query as a CLEAN, SPECIFIC question for a SQL agent
4. Determine if RAG context would help

IMPORTANT:
- Each query should be standalone and clear
- Do NOT include chat history or conversational context
- Format as: "From [table], show [columns] where [conditions]"
- Be specific about what data to retrieve

Respond in JSON:
{{
    "needs_decomposition": true/false,
    "complexity": "simple"/"complex",
    "query_plan": [
        {{
            "step": 1,
            "description": "What this query does",
            "tables": ["table1"],
            "clean_question": "From sales_table, show sentiment_score by city for November 2025"
        }}
    ],
    "execution_mode": "genie_only" or "rag_only" or "genie_and_rag",
    "reasoning": "Why this approach"
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a query planning expert. Always respond with valid JSON."),
                HumanMessage(content=planning_prompt)
            ])

            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            # Extract formatted queries
            formatted_queries = [
                step["clean_question"]
                for step in result.get("query_plan", [])
            ]

            logger.info(f"Query plan created: {len(formatted_queries)} queries, "
                       f"mode={result.get('execution_mode')}")

            return {
                "needs_decomposition": result.get("needs_decomposition", False),
                "query_plan": result.get("query_plan", []),
                "formatted_queries": formatted_queries,
                "execution_mode": result.get("execution_mode", "genie_only"),
                "reasoning": result.get("reasoning", "")
            }

        except Exception as e:
            logger.error(f"Query planning error: {e}")
            # Fallback: create simple query
            simple_query = f"From {', '.join(relevant_tables)}, answer: {question}"
            return {
                "needs_decomposition": False,
                "query_plan": [{
                    "step": 1,
                    "description": "Direct query",
                    "tables": relevant_tables,
                    "clean_question": simple_query
                }],
                "formatted_queries": [simple_query],
                "execution_mode": "genie_only",
                "reasoning": f"Fallback due to error: {e}"
            }


def create_query_planner_node(query_planner: QueryPlannerAgent):
    """Create LangGraph node for query planning"""

    def query_planner_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Plan query execution"""

        # Get question and schema info
        question = state["original_question"]
        relevant_tables = state["relevant_tables"]
        relevant_columns = state["relevant_columns"]
        needs_rag = state.get("needs_rag", False)

        # Plan queries
        plan = query_planner.plan_queries(
            question=question,
            relevant_tables=relevant_tables,
            relevant_columns=relevant_columns,
            needs_rag=needs_rag
        )

        return {
            "query_plan": plan["query_plan"],
            "needs_decomposition": plan["needs_decomposition"],
            "formatted_queries": plan["formatted_queries"],
            "execution_mode": plan["execution_mode"],
            "messages": [AIMessage(content=f"Query Plan: {plan['reasoning']}")]
        }

    return query_planner_node


# ============================================================================
# 3. GENIE EXECUTOR AGENT - Clean SQL Execution
# ============================================================================

def create_genie_executor():
    """Create Genie executor that sends CLEAN formatted questions"""

    # Initialize Genie
    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    genie_agent = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="SQL_Specialist",
        description="Execute clean, specific SQL queries on Unity Catalog",
        client=workspace_client,
        return_pandas=False,
    )

    def genie_executor_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Execute formatted queries via Genie"""

        formatted_queries = state["formatted_queries"]
        results = []

        logger.info(f"Executing {len(formatted_queries)} queries via Genie")

        for idx, query in enumerate(formatted_queries):
            try:
                logger.info(f"Genie Query {idx+1}: {query}")

                # Execute CLEAN query (not chat history!)
                result = genie_agent.invoke({"question": query})

                # Extract result
                result_text = result if isinstance(result, str) else str(result)
                results.append(result_text)

                logger.info(f"Genie Query {idx+1} completed")

            except Exception as e:
                logger.error(f"Genie query {idx+1} failed: {e}")
                results.append(f"Query failed: {e}")

        # Combine results
        combined_result = "\n\n".join([
            f"Query {i+1} Result:\n{r}"
            for i, r in enumerate(results)
        ])

        return {
            "genie_results": results,
            "messages": [AIMessage(content=f"SQL Results:\n{combined_result}")]
        }

    logger.info("Genie Executor created")
    return genie_executor_node


# ============================================================================
# 4. RAG AGENT - Document Context
# ============================================================================

def create_rag_agent():
    """Create RAG agent for document context"""
    try:
        docs = load_documents_from_directory("./data/documents")

        if not docs:
            logger.warning("No documents found - RAG agent not available")
            return None

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        splits = text_splitter.split_documents(docs)

        # Create embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.embedding_deployment,
            api_version=config.azure_openai.api_version,
        )

        # Check for existing FAISS index
        import os
        faiss_index_path = "./data/faiss_rag_index"

        if os.path.exists(f"{faiss_index_path}/index.faiss"):
            logger.info(f"Loading existing FAISS index from {faiss_index_path}")
            vectorstore = FAISS.load_local(
                faiss_index_path,
                embeddings,
                allow_dangerous_deserialization=True
            )
        else:
            logger.info("Creating new FAISS index")
            vectorstore = FAISS.from_documents(splits, embeddings)
            os.makedirs(faiss_index_path, exist_ok=True)
            vectorstore.save_local(faiss_index_path)

        # Create retriever tool
        rag_tool = create_retriever_tool(
            vectorstore.as_retriever(search_kwargs={"k": 5}),
            "document_search",
            "Search company documents, policies, and procedures"
        )

        logger.info("RAG Agent created successfully")
        return rag_tool

    except Exception as e:
        logger.error(f"Failed to create RAG agent: {e}")
        return None


def create_rag_executor_node(rag_tool):
    """Create RAG executor node"""

    if rag_tool is None:
        return None

    def rag_executor_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Execute RAG retrieval"""

        question = state["original_question"]

        try:
            logger.info(f"RAG retrieval for: {question}")

            # Execute retrieval
            result = rag_tool.invoke({"query": question})

            return {
                "rag_results": [result],
                "messages": [AIMessage(content=f"Document Context:\n{result}")]
            }

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return {
                "rag_results": [],
                "messages": [AIMessage(content=f"Document retrieval failed: {e}")]
            }

    return rag_executor_node


# ============================================================================
# 5. VALIDATION AGENT - Result Quality Check
# ============================================================================

class ValidationAgent:
    """Validates if results answer the original question"""

    def __init__(self):
        self.llm = AzureChatOpenAI(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.gpt4o_deployment,
            api_version=config.azure_openai.api_version,
            temperature=0.0,
        )
        logger.info("Validation Agent initialized")

    def validate(self,
                question: str,
                genie_results: List[str],
                rag_results: List[str]) -> Dict[str, Any]:
        """
        Validate if results answer the question.

        Returns:
            Dict with:
                - status: "complete", "incomplete", "needs_clarification"
                - feedback: str
                - confidence: float
        """

        # Combine results
        all_results = "SQL Results:\n" + "\n".join(genie_results) if genie_results else ""
        all_results += "\n\nDocument Results:\n" + "\n".join(rag_results) if rag_results else ""

        validation_prompt = f"""You are a result validation expert.

ORIGINAL QUESTION:
{question}

RESULTS OBTAINED:
{all_results}

Evaluate:
1. Do these results fully answer the question?
2. Is any information missing?
3. Is clarification needed from the user?

Respond in JSON:
{{
    "status": "complete" or "incomplete" or "needs_clarification",
    "confidence": 0.0-1.0,
    "feedback": "explanation",
    "missing_aspects": [] or ["aspect1", "aspect2"]
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a validation expert. Always respond with valid JSON."),
                HumanMessage(content=validation_prompt)
            ])

            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))

            logger.info(f"Validation: status={result.get('status')}, "
                       f"confidence={result.get('confidence')}")

            return {
                "status": result.get("status", "incomplete"),
                "feedback": result.get("feedback", ""),
                "confidence": result.get("confidence", 0.0),
                "missing_aspects": result.get("missing_aspects", [])
            }

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "status": "incomplete",
                "feedback": f"Validation error: {e}",
                "confidence": 0.0,
                "missing_aspects": []
            }


def create_validation_node(validation_agent: ValidationAgent):
    """Create validation node"""

    def validation_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Validate results"""

        question = state["original_question"]
        genie_results = state.get("genie_results", [])
        rag_results = state.get("rag_results", [])

        validation = validation_agent.validate(question, genie_results, rag_results)

        # Determine next agent based on validation
        if validation["status"] == "complete":
            next_agent = "synthesis"
        elif validation["status"] == "needs_clarification":
            next_agent = "human"
        else:
            # Incomplete - could replan or ask human
            iterations = state.get("iterations", 0)
            if iterations >= 3:
                next_agent = "human"
            else:
                next_agent = "query_planner"  # Try replanning

        return {
            "validation_status": validation["status"],
            "validation_feedback": validation["feedback"],
            "next_agent": next_agent,
            "messages": [AIMessage(content=f"Validation: {validation['feedback']}")]
        }

    return validation_node


# ============================================================================
# 6. ENHANCED SUPERVISOR - Orchestration
# ============================================================================

def create_enhanced_supervisor():
    """Create enhanced supervisor that coordinates all agents"""

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.7,
    )

    system_prompt = """You are an enhanced supervisor coordinating a team of specialist agents.

AGENT PIPELINE:
1. Schema Agent → Analyzes Unity Catalog tables/columns
2. Query Planner → Breaks down complex questions, formats clean queries
3. Executors → Genie (SQL) and/or RAG (documents)
4. Validation → Checks if results answer the question
5. Synthesis → Creates final answer

YOUR ROLE:
- Start by routing to "schema" for analysis
- After schema, route to "query_planner"
- After planning, route based on execution_mode:
  * "genie_only" → "genie_executor"
  * "rag_only" → "rag_executor"
  * "genie_and_rag" → "parallel_executor"
- After execution, route to "validation"
- After validation, follow its recommendation
- If unclear, route to "human"

AVAILABLE AGENTS:
- schema
- query_planner
- genie_executor
- rag_executor (if documents available)
- parallel_executor (both Genie + RAG)
- validation
- synthesis
- human

ROUTING RULES:
- First call: Always "schema"
- After schema: "query_planner"
- After query_planner: Check execution_mode
- After executors: "validation"
- After validation: Follow next_agent from validation
- If iterations > 5: "human"

Respond with ONLY the agent name."""

    def supervisor_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Enhanced supervisor routing"""

        messages = state["messages"]
        iterations = state.get("iterations", 0)

        # Check iteration limit
        if iterations >= 5:
            return {
                "next_agent": "human",
                "iterations": iterations + 1
            }

        # Determine routing based on state
        last_message = messages[-1].content if messages else ""

        # Check if we have schema analysis
        if "Schema Analysis" not in str(messages):
            next_agent = "schema"
        # Check if we have query plan
        elif "Query Plan" not in str(messages):
            next_agent = "query_planner"
        # Check if we need execution
        elif state.get("formatted_queries") and not state.get("genie_results"):
            execution_mode = state.get("execution_mode", "genie_only")
            if execution_mode == "genie_only":
                next_agent = "genie_executor"
            elif execution_mode == "rag_only":
                next_agent = "rag_executor"
            else:
                next_agent = "parallel_executor"
        # Check if we need validation
        elif (state.get("genie_results") or state.get("rag_results")) and not state.get("validation_status"):
            next_agent = "validation"
        # Follow validation recommendation
        elif state.get("validation_status"):
            next_agent = state.get("next_agent", "synthesis")
        else:
            # Fallback: ask LLM
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                *messages
            ])
            next_agent = response.content.strip()

        logger.info(f"Supervisor routing to: {next_agent} (iteration {iterations})")

        return {
            "next_agent": next_agent,
            "iterations": iterations + 1
        }

    return supervisor_node


# ============================================================================
# 7. SYNTHESIS AGENT
# ============================================================================

def create_synthesis_agent():
    """Create synthesis agent"""

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.3,
    )

    def synthesis_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Synthesize final answer"""

        messages = state["messages"]
        question = state["original_question"]
        genie_results = state.get("genie_results", [])
        rag_results = state.get("rag_results", [])

        synthesis_prompt = f"""Synthesize a comprehensive answer from all available information.

ORIGINAL QUESTION:
{question}

SQL RESULTS:
{chr(10).join(genie_results) if genie_results else "No SQL results"}

DOCUMENT CONTEXT:
{chr(10).join(rag_results) if rag_results else "No document context"}

Create a clear, comprehensive answer that:
1. Directly answers the question
2. Cites sources (SQL data, documents)
3. Provides insights and context
4. Is well-formatted and easy to read"""

        response = llm.invoke([
            SystemMessage(content="You are a synthesis expert creating final answers."),
            HumanMessage(content=synthesis_prompt)
        ])

        return {
            "final_answer": response.content,
            "next_agent": "FINISH",
            "messages": [response]
        }

    return synthesis_node


# ============================================================================
# 8. HUMAN NODE
# ============================================================================

def create_human_node():
    """Create human clarification node"""

    def human_node(state: EnhancedAgentState) -> Dict[str, Any]:
        """Ask human for clarification"""

        missing_info = state.get("missing_information", [])
        validation_feedback = state.get("validation_feedback", "")

        clarification_items = []
        if missing_info:
            clarification_items.extend(missing_info)

        if not clarification_items:
            clarification_items = [
                "Which specific data source or table?",
                "What metrics or columns are you interested in?",
                "What time period or filters should apply?"
            ]

        clarification_msg = f"""I need clarification to answer your question accurately:

{chr(10).join(f"- {item}" for item in clarification_items)}

{validation_feedback if validation_feedback else "Please provide the missing details."}"""

        return {
            "final_answer": clarification_msg,
            "next_agent": "FINISH",
            "messages": [AIMessage(content=clarification_msg)]
        }

    return human_node


# ============================================================================
# 9. BUILD ENHANCED GRAPH
# ============================================================================

def create_enhanced_multi_agent_graph():
    """
    Build complete enhanced multi-agent graph.

    Returns:
        Compiled LangGraph with all agents
    """

    logger.info("Building enhanced multi-agent graph v4.0")

    # Initialize agents
    schema_agent = SchemaAgent()
    query_planner = QueryPlannerAgent()
    validation_agent = ValidationAgent()

    # Create nodes
    schema_node = create_schema_node(schema_agent)
    query_planner_node = create_query_planner_node(query_planner)
    genie_executor_node = create_genie_executor()
    rag_tool = create_rag_agent()
    rag_executor_node = create_rag_executor_node(rag_tool) if rag_tool else None
    validation_node = create_validation_node(validation_agent)
    supervisor_node = create_enhanced_supervisor()
    synthesis_node = create_synthesis_agent()
    human_node = create_human_node()

    # Build workflow
    workflow = StateGraph(EnhancedAgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("schema", schema_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("genie_executor", genie_executor_node)
    if rag_executor_node:
        workflow.add_node("rag_executor", rag_executor_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("human", human_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Define routing
    def route_from_supervisor(state: EnhancedAgentState) -> str:
        next_agent = state.get("next_agent", "schema")
        if next_agent == "FINISH":
            return "synthesis"
        return next_agent

    # Build routing options
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

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        routing_options
    )

    # All agents loop back to supervisor
    workflow.add_edge("schema", "supervisor")
    workflow.add_edge("query_planner", "supervisor")
    workflow.add_edge("genie_executor", "supervisor")
    if rag_executor_node:
        workflow.add_edge("rag_executor", "supervisor")
    workflow.add_edge("validation", "supervisor")

    # Terminal nodes
    workflow.add_edge("synthesis", END)
    workflow.add_edge("human", END)

    # Add memory
    memory = MemorySaver()

    # Compile
    graph = workflow.compile(checkpointer=memory)

    logger.info("✅ Enhanced multi-agent graph v4.0 created successfully")

    return graph


# ============================================================================
# 10. HELPER FUNCTION
# ============================================================================

def get_enhanced_agent():
    """Get compiled enhanced agent graph"""
    return create_enhanced_multi_agent_graph()


if __name__ == "__main__":
    # Test initialization
    agent = get_enhanced_agent()
    print("✅ Enhanced Multi-Agent System v4.0 initialized successfully")
