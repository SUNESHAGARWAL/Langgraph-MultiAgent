"""
Multi-Agent Orchestrator using LangChain Deep Agents

This module creates a Deep Agent with:
- Databricks Genie for SQL queries (via databricks_langchain.GenieAgent)
- Vector Search for RAG (via databricks_langchain.VectorSearchRetrieverTool)
- Custom tools for Azure Blob Storage RAG monitoring
- TodoListMiddleware for planning and task management

Architecture:
- Uses LangChain's create_agent (not custom orchestrator)
- Uses built-in middleware (TodoListMiddleware)
- Leverages Databricks pre-built integrations
- Minimal custom code, maximum library usage
"""

from typing import List, Optional
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.tools import tool

# Databricks integrations
from databricks_langchain.genie import GenieAgent
from databricks_langchain.vectorsearch import VectorSearchRetrieverTool

from src.core.config import config
from src.utils.logging import get_logger
from src.services.storage import get_storage_service

logger = get_logger(__name__)


def create_rag_retriever_tool():
    """
    Create vector search retriever tool for RAG using Databricks Vector Search.

    If you have a Databricks Vector Search index set up, use VectorSearchRetrieverTool.
    Otherwise, this returns None and we'll use Azure Blob Storage monitoring.
    """
    # TODO: Configure if you have Databricks Vector Search index
    vector_search_index = None  # Set to your index name if available

    if vector_search_index:
        return VectorSearchRetrieverTool(
            index_name=vector_search_index,
            num_results=5,
            tool_name="search_documents",
            tool_description="Search through uploaded documents and knowledge base",
        )

    # Fallback: Custom Azure Blob Storage RAG tool
    return create_azure_blob_rag_tool()


@tool
def create_azure_blob_rag_tool():
    """
    Search and retrieve documents from Azure Blob Storage.

    This tool monitors the configured Azure Blob Storage container for RAG documents
    and provides semantic search over the indexed content.

    Returns:
        Relevant document chunks based on the query
    """
    from src.services.vector_store import get_vector_store

    def search_documents(query: str, top_k: int = 5) -> str:
        """
        Search through uploaded documents in Azure Blob Storage.

        Args:
            query: Natural language query to search for
            top_k: Number of results to return (default: 5)

        Returns:
            Relevant document excerpts
        """
        vector_store = get_vector_store("rag_documents")

        try:
            results = vector_store.similarity_search(
                query=query,
                k=top_k,
                score_threshold=0.7,
            )

            if not results:
                return "No relevant documents found."

            output = [f"Found {len(results)} relevant documents:\n"]

            for i, (doc, score) in enumerate(results, 1):
                metadata = doc.metadata
                source = metadata.get("source", "Unknown")
                output.append(f"{i}. Source: {source} (relevance: {score:.2f})")
                output.append(f"   Content: {doc.page_content[:200]}...")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return f"Error searching documents: {str(e)}"

    return search_documents


def create_multi_agent_orchestrator():
    """
    Create the multi-agent orchestrator using LangChain and Deep Agents.

    Returns:
        Configured agent ready to handle user queries
    """
    logger.info("Initializing Multi-Agent Orchestrator")

    # 1. Initialize LLM (Azure OpenAI)
    model = init_chat_model(
        model=f"azure_openai/{config.azure_openai.gpt4o_deployment}",
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    logger.info(f"Initialized Azure OpenAI model: {config.azure_openai.gpt4o_deployment}")

    # 2. Create Genie Agent for SQL queries
    genie_tool = GenieAgent(
        genie_space_id=config.databricks.genie_space_id,
        genie_agent_name="Databricks_Genie",
        description=f"Execute natural language SQL queries on Unity Catalog. "
                   f"Has access to tables: {', '.join(config.databricks.unity_tables)}. "
                   f"Use this for structured data questions about sales, customers, products, etc.",
    )

    logger.info(f"Initialized Genie Agent: {config.databricks.genie_space_id}")

    # 3. Create RAG retriever tool
    rag_tool = create_rag_retriever_tool()

    # 4. Collect all tools
    tools = [genie_tool]

    if rag_tool:
        tools.append(rag_tool)
        logger.info("Added RAG retriever tool")

    # 5. Create agent with TodoListMiddleware
    agent = create_agent(
        model=model,
        tools=tools,
        middleware=[
            TodoListMiddleware(
                system_prompt="""
You are a data analysis assistant with access to:
- Databricks Genie: For querying Unity Catalog tables with natural language
- Document search: For retrieving information from uploaded documents

When given a complex task:
1. Use write_todos to break it down into steps
2. Execute each step using the appropriate tool
3. Synthesize the results into a clear answer

Always:
- Be specific and data-driven in your responses
- Cite sources (SQL queries, documents, tables)
- If you need clarification, ask the user
- Update todos as you make progress
"""
            ),
        ],
    )

    logger.info("Multi-Agent Orchestrator initialized successfully")

    return agent


# Singleton instance
_orchestrator: Optional[object] = None


def get_orchestrator():
    """Get or create the singleton orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_multi_agent_orchestrator()
    return _orchestrator
