"""
Multi-Agent Orchestrator using LangGraph Supervisor Pattern

Architecture:
- Supervisor Agent: Orchestrates and routes to specialists
- Genie Agent: SQL queries on Unity Catalog
- RAG Agent: Document retrieval and search
- Synthesis Agent: Combines results from multiple agents
- Human Agent: Asks clarifying questions when needed

The supervisor decides which agent(s) to call, can replan, and iterates until complete.
"""

from typing import Annotated, Literal, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
try:
    from langchain_core.tools import create_retriever_tool
except ImportError:
    from langchain.tools.retriever import create_retriever_tool
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from databricks_langchain.genie import GenieAgent
from databricks.sdk import WorkspaceClient
import functools
import operator

from src.core.config import config
from src.utils.logging import get_logger
from src.utils.parsers import load_documents_from_directory

logger = get_logger(__name__)


# ============================================================================
# 1. AGENT STATE
# ============================================================================

class AgentState(TypedDict):
    """State for multi-agent system"""
    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str  # Which agent to call next
    iterations: int  # Track iterations to prevent infinite loops
    final_answer: str  # Final synthesized answer


# ============================================================================
# 2. SPECIALIST AGENTS
# ============================================================================

def create_genie_agent():
    """Create Genie specialist agent for SQL queries"""
    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    genie_tool = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="SQL_Specialist",
        description=f"""SQL query specialist. Use ONLY for:
        - Querying sales, revenue, transaction data
        - Customer analytics and demographics
        - Product performance and inventory
        - Any data/analytics questions requiring SQL

        Available tables: {', '.join(config.databricks.unity_tables)}

        Returns: Query results as markdown tables""",
        client=workspace_client,
        return_pandas=False,
    )

    logger.info("Created Genie specialist agent")
    return genie_tool


def create_rag_agent():
    """Create RAG specialist agent for document retrieval"""
    try:
        # Load documents
        docs = load_documents_from_directory("./data/documents")

        if not docs:
            logger.warning("No documents found - RAG agent not available")
            return None

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.embedding.chunk_size,
            chunk_overlap=config.embedding.chunk_overlap,
        )
        splits = text_splitter.split_documents(docs)

        logger.info(f"Split {len(docs)} documents into {len(splits)} chunks")

        # Create embeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=config.azure_openai.endpoint,
            api_key=config.azure_openai.api_key,
            azure_deployment=config.azure_openai.embedding_deployment,
            api_version=config.azure_openai.api_version,
        )

        # Create vector store
        vectorstore = FAISS.from_documents(splits, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        # Create retriever tool
        rag_tool = create_retriever_tool(
            retriever,
            "document_search",
            """Document search specialist. Use ONLY for:
            - Company policies, procedures, guidelines
            - Technical documentation and manuals
            - Reference materials from uploaded PDFs/DOCX
            - Knowledge base articles

            Do NOT use for real-time data or analytics.

            Returns: Relevant document excerpts with sources""",
        )

        logger.info("Created RAG specialist agent")
        return rag_tool

    except Exception as e:
        logger.warning(f"Failed to create RAG agent: {e}")
        return None


# ============================================================================
# 3. SUPERVISOR AGENT (ORCHESTRATOR)
# ============================================================================

def create_supervisor_agent(agents: list):
    """
    Create supervisor agent that routes to specialists.

    The supervisor:
    1. Analyzes the user question
    2. Decides which specialist(s) to call
    3. Can replan if results are insufficient
    4. Synthesizes final answer
    5. Asks human if stuck
    """
    model = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    # Available agent names
    agent_names = [a.name if hasattr(a, 'name') else str(a) for a in agents if a is not None]
    options = ["FINISH"] + agent_names + ["HUMAN"]

    system_prompt = f"""You are a supervisor agent coordinating a team of specialists:

AVAILABLE SPECIALISTS:
{chr(10).join(f'- {name}' for name in agent_names)}

YOUR ROLE:
1. Analyze user questions
2. Route to appropriate specialist(s)
3. Replan if results are insufficient
4. Synthesize final answers
5. Ask HUMAN for clarification when needed

ROUTING RULES:
- For data/SQL queries → SQL_Specialist
- For document/policy questions → document_search
- If unsure or need clarification → HUMAN
- When you have complete answer → FINISH

IMPORTANT:
- You can call multiple specialists
- You can replan and retry
- Always synthesize results clearly
- Cite sources
- If stuck after 3 iterations → ask HUMAN

Respond with ONLY the next agent name: {', '.join(options)}"""

    def supervisor_node(state: AgentState):
        """Supervisor decides which agent to call next"""
        messages = state["messages"]
        iterations = state.get("iterations", 0)

        # Check iteration limit
        if iterations >= 5:
            return {
                "next_agent": "HUMAN",
                "messages": [AIMessage(content="I've tried multiple approaches but need your help. Could you provide more details?")],
                "iterations": iterations + 1
            }

        # Ask supervisor to route
        response = model.invoke([
            SystemMessage(content=system_prompt),
            *messages
        ])

        # Extract next agent from response
        next_agent = response.content.strip()

        # Validate
        if next_agent not in options:
            next_agent = "FINISH"

        logger.info(f"Supervisor routing to: {next_agent} (iteration {iterations})")

        return {
            "next_agent": next_agent,
            "messages": [response],
            "iterations": iterations + 1
        }

    return supervisor_node


# ============================================================================
# 4. SYNTHESIS AGENT
# ============================================================================

def create_synthesis_agent():
    """Create agent that synthesizes results from multiple specialists"""
    model = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=0.3,  # Lower temperature for consistent synthesis
    )

    system_prompt = """You are a synthesis specialist. Your job is to:

1. Combine results from multiple agents
2. Create a coherent, comprehensive answer
3. Cite all sources clearly
4. Format nicely for the user

When synthesizing:
- Combine SQL results and document excerpts
- Highlight key findings
- Use markdown formatting
- Always cite sources (e.g., "According to sales_data table..." or "From policy document...")
- Be concise but complete"""

    def synthesis_node(state: AgentState):
        """Synthesize final answer from all agent responses"""
        messages = state["messages"]

        response = model.invoke([
            SystemMessage(content=system_prompt),
            *messages,
            HumanMessage(content="Please synthesize the above information into a final answer.")
        ])

        return {
            "messages": [response],
            "final_answer": response.content,
            "next_agent": "FINISH"
        }

    return synthesis_node


# ============================================================================
# 5. HUMAN-IN-THE-LOOP AGENT
# ============================================================================

def create_human_node():
    """Create node that asks human for input"""

    def human_node(state: AgentState):
        """Ask human for clarification"""
        messages = state["messages"]

        # Extract what we're confused about
        last_message = messages[-1].content if messages else "I need clarification"

        # In CLI, this will pause and wait for input
        # In production, you'd handle this differently (webhook, queue, etc.)
        return {
            "messages": [AIMessage(content=f"Asking human for clarification: {last_message}")],
            "next_agent": "FINISH"  # For now, finish after asking
        }

    return human_node


# ============================================================================
# 6. BUILD MULTI-AGENT GRAPH
# ============================================================================

def create_multi_agent_graph():
    """
    Create multi-agent graph with supervisor pattern.

    Flow:
    1. User question → Supervisor
    2. Supervisor → Specialist(s)
    3. Specialist → Supervisor (with results)
    4. Supervisor → Synthesis or Replan
    5. Synthesis → Final Answer
    """
    logger.info("Creating multi-agent graph")

    # Create specialist agents
    genie_agent = create_genie_agent()
    rag_agent = create_rag_agent()

    # Collect available agents
    agents = [genie_agent, rag_agent]

    # Create supervisor
    supervisor = create_supervisor_agent(agents)

    # Create synthesis agent
    synthesis = create_synthesis_agent()

    # Create human node
    human = create_human_node()

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("synthesis", synthesis)
    workflow.add_node("human", human)

    # Add specialist nodes (as tools)
    if genie_agent:
        workflow.add_node("SQL_Specialist", ToolNode([genie_agent]))
    if rag_agent:
        workflow.add_node("document_search", ToolNode([rag_agent]))

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add conditional edges from supervisor
    def route_from_supervisor(state: AgentState):
        """Route based on supervisor's decision"""
        next_agent = state.get("next_agent", "FINISH")

        if next_agent == "FINISH":
            return "synthesis"
        elif next_agent == "HUMAN":
            return "human"
        else:
            return next_agent

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "synthesis": "synthesis",
            "human": "human",
            "SQL_Specialist": "SQL_Specialist",
            "document_search": "document_search",
        }
    )

    # All specialists return to supervisor
    if genie_agent:
        workflow.add_edge("SQL_Specialist", "supervisor")
    if rag_agent:
        workflow.add_edge("document_search", "supervisor")

    # Synthesis and human end
    workflow.add_edge("synthesis", END)
    workflow.add_edge("human", END)

    # Add memory for conversation history
    memory = MemorySaver()

    # Compile
    graph = workflow.compile(checkpointer=memory)

    logger.info("Multi-agent graph created successfully")
    return graph


# ============================================================================
# 7. SINGLETON
# ============================================================================

_agent_graph = None


def get_agent():
    """Get or create singleton agent graph"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_multi_agent_graph()
    return _agent_graph
