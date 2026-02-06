"""
Multi-Agent System using LangGraph

Clean implementation using:
- LangGraph StateGraph (not custom orchestration)
- Databricks GenieAgent (pre-built)
- LangChain retriever tools (not custom)
- Simple, minimal code
"""

from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.tools.retriever import create_retriever_tool
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from databricks_langchain.genie import GenieAgent

from src.core.config import config
from src.utils.logging import get_logger
from src.utils.parsers import load_documents_from_directory

logger = get_logger(__name__)


def create_vector_store():
    """
    Create FAISS vector store from documents.

    Simple implementation - loads documents once and creates vector store.
    No complex monitoring, caching, or Azure Blob integration.
    """
    try:
        logger.info("Creating vector store from documents")

        # Load documents (if any exist)
        docs = load_documents_from_directory("./data/documents")

        if not docs:
            logger.warning("No documents found - RAG will not be available")
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

        logger.info("Vector store created successfully")
        return vectorstore

    except Exception as e:
        logger.warning(f"Failed to create vector store: {e}")
        return None


def create_retriever_tool_if_available(vectorstore):
    """Create retriever tool if vector store exists"""
    if vectorstore is None:
        return None

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    return create_retriever_tool(
        retriever,
        "search_documents",
        "Search through uploaded documents and knowledge base. "
        "Use this to find information from PDF, DOCX, and other uploaded files.",
    )


def create_agent_graph():
    """
    Create LangGraph agent with tools.

    Uses StateGraph with:
    - Databricks GenieAgent for SQL queries
    - Retriever tool for RAG (if documents available)
    - Simple message-based state
    """
    logger.info("Creating agent graph")

    # 1. Initialize LLM
    model = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        azure_deployment=config.azure_openai.gpt4o_deployment,
        api_version=config.azure_openai.api_version,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    # 2. Create Databricks WorkspaceClient for authentication
    from databricks.sdk import WorkspaceClient

    workspace_client = WorkspaceClient(
        host=config.databricks.host,
        token=config.databricks.token,
    )

    # 3. Create tools
    tools = []

    # Genie tool for SQL queries
    genie_tool = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="Databricks_Genie",
        description=f"Execute natural language SQL queries on Unity Catalog. "
                   f"Has access to tables: {', '.join(config.databricks.unity_tables)}. "
                   f"Use this for questions about data, analytics, sales, customers, products, etc.",
        client=workspace_client,  # Proper authentication
        return_pandas=False,  # Return markdown strings (easier for LLM)
    )
    tools.append(genie_tool)

    logger.info(f"Initialized GenieAgent with space ID: {config.databricks.genie_space_id}")

    # Retriever tool for RAG (if available)
    vectorstore = create_vector_store()
    retriever_tool = create_retriever_tool_if_available(vectorstore)
    if retriever_tool:
        tools.append(retriever_tool)
        logger.info("Added retriever tool for RAG")
    else:
        logger.info("No retriever tool - RAG not available")

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    # 4. Define agent node
    def agent_node(state: MessagesState):
        """Agent node that calls LLM with tools"""
        messages = state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    # 5. Build LangGraph StateGraph
    workflow = StateGraph(MessagesState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Compile
    graph = workflow.compile()

    logger.info("Agent graph created successfully")
    return graph


# Singleton instance
_agent_graph = None


def get_agent():
    """Get or create singleton agent graph"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph
