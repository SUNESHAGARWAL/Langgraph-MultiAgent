"""
Genie Agent for interacting with Databricks Genie Space.
Handles natural language to SQL conversion and query execution on Unity Catalog.
"""

import time
from typing import Dict, Any, Optional, List
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import GenieMessageQueryResultsRequest

from src.core.config import config
from src.services.caching import get_smart_cache
from src.services.mlflow_tracker import get_mlflow_tracker, track_agent
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class GenieAgent:
    """
    Agent for interacting with Databricks Genie Space.
    Converts natural language questions to SQL and executes on Unity Catalog.
    """

    def __init__(self):
        self.client = self._initialize_client()
        self.space_id = config.databricks.genie_space_id
        self.timeout = config.databricks.genie_timeout
        self.cache = get_smart_cache()
        self.tracker = get_mlflow_tracker()

        logger.info(
            f"Initialized GenieAgent",
            space_id=self.space_id,
            timeout=self.timeout,
        )

    def _initialize_client(self) -> WorkspaceClient:
        """Initialize Databricks WorkspaceClient"""
        try:
            client = WorkspaceClient(
                host=config.databricks.host,
                token=config.databricks.token,
            )
            logger.info("Initialized Databricks WorkspaceClient")
            return client

        except Exception as e:
            logger.error(f"Failed to initialize Databricks client: {e}")
            raise

    @trace_function("genie_query")
    @track_agent("genie_agent")
    def query(
        self,
        question: str,
        use_cache: bool = True,
        max_retries: int = None,
    ) -> Dict[str, Any]:
        """
        Query Genie with a natural language question.

        Args:
            question: Natural language question
            use_cache: Whether to use semantic cache
            max_retries: Maximum retries on failure (defaults to config)

        Returns:
            Dict with query results, SQL, and metadata
        """
        if max_retries is None:
            max_retries = config.agent.max_retries

        start_time = time.time()

        # Check cache first
        if use_cache:
            cache_results = self.cache.search_similar(
                query=question,
                top_k=1,
                tags=["genie_query"],
            )

            if cache_results:
                cache_key, cached_value, similarity = cache_results[0]
                cache_latency = time.time() - start_time

                logger.info(
                    f"Cache hit for Genie query",
                    similarity=similarity,
                    latency=cache_latency,
                )

                self.tracker.log_query_cache_performance(
                    query=question,
                    cache_hit=True,
                    similarity_score=similarity,
                    latency=cache_latency,
                )

                return {
                    "success": True,
                    "cached": True,
                    "similarity_score": similarity,
                    **cached_value,
                }

        # Execute Genie query with retries
        for attempt in range(max_retries + 1):
            try:
                result = self._execute_genie_query(question)

                latency = time.time() - start_time

                # Cache the result
                if use_cache and result["success"]:
                    self.cache.set(
                        key=question,
                        value=result,
                        tags=["genie_query"],
                    )

                self.tracker.log_query_cache_performance(
                    query=question,
                    cache_hit=False,
                    latency=latency,
                )

                logger.info(
                    f"Genie query successful",
                    attempt=attempt + 1,
                    latency=latency,
                )

                return result

            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Genie query failed, retrying in {wait_time}s",
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Genie query failed after {max_retries} retries: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "question": question,
                        "attempts": attempt + 1,
                    }

    def _execute_genie_query(self, question: str) -> Dict[str, Any]:
        """
        Execute a query using Genie API.

        Args:
            question: Natural language question

        Returns:
            Query results with metadata
        """
        try:
            # Create a conversation in the Genie space
            conversation = self.client.genie.create_message(
                space_id=self.space_id,
                content=question,
            )

            conversation_id = conversation.id
            message_id = conversation.message_id

            logger.info(
                f"Created Genie conversation",
                conversation_id=conversation_id,
                message_id=message_id,
            )

            # Poll for results
            start_time = time.time()
            while True:
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(
                        f"Genie query timeout after {self.timeout} seconds"
                    )

                # Get message status
                message = self.client.genie.get_message(
                    space_id=self.space_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )

                status = message.status.value if hasattr(message, "status") else None

                if status == "COMPLETED":
                    # Get query results
                    results = self.client.genie.get_message_query_result(
                        space_id=self.space_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                    )

                    return self._parse_genie_results(results, message)

                elif status in ["FAILED", "CANCELLED"]:
                    error_msg = getattr(message, "error", "Unknown error")
                    raise Exception(f"Genie query failed: {error_msg}")

                # Still processing, wait and retry
                time.sleep(2)

        except Exception as e:
            logger.error(f"Error executing Genie query: {e}")
            raise

    def _parse_genie_results(self, results: Any, message: Any) -> Dict[str, Any]:
        """
        Parse Genie query results into a standardized format.

        Args:
            results: Genie query results
            message: Genie message object

        Returns:
            Parsed results dict
        """
        try:
            # Extract SQL query if available
            sql_query = None
            if hasattr(message, "query"):
                sql_query = message.query.query if hasattr(message.query, "query") else None

            # Extract data rows
            data_rows = []
            columns = []

            if hasattr(results, "statement_response"):
                statement = results.statement_response

                # Get column names
                if hasattr(statement, "manifest") and statement.manifest:
                    columns = [
                        col.name for col in statement.manifest.schema.columns
                    ] if hasattr(statement.manifest, "schema") else []

                # Get data rows
                if hasattr(statement, "result") and statement.result:
                    if hasattr(statement.result, "data_array"):
                        data_rows = statement.result.data_array

            # Format as list of dicts
            formatted_data = []
            if columns and data_rows:
                for row in data_rows:
                    row_dict = dict(zip(columns, row))
                    formatted_data.append(row_dict)

            # Extract description/summary if available
            description = None
            if hasattr(message, "content"):
                description = message.content

            result = {
                "success": True,
                "cached": False,
                "sql_query": sql_query,
                "columns": columns,
                "data": formatted_data,
                "row_count": len(formatted_data),
                "description": description,
                "message_id": message.id if hasattr(message, "id") else None,
            }

            logger.info(
                f"Parsed Genie results",
                row_count=len(formatted_data),
                columns=len(columns),
            )

            return result

        except Exception as e:
            logger.error(f"Error parsing Genie results: {e}")
            raise

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history from Genie.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """
        try:
            messages = self.client.genie.list_messages(
                space_id=self.space_id,
                conversation_id=conversation_id,
                max_results=limit,
            )

            history = []
            for msg in messages:
                history.append({
                    "id": msg.id,
                    "content": msg.content if hasattr(msg, "content") else None,
                    "role": msg.role.value if hasattr(msg, "role") else None,
                    "timestamp": msg.created_timestamp if hasattr(msg, "created_timestamp") else None,
                })

            return history

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    def clear_cache(self):
        """Clear Genie query cache"""
        # This would require listing and deleting all cache entries with 'genie_query' tag
        logger.info("Cache clearing not fully implemented for tag-based deletion")


# Global Genie agent instance
_genie_agent = None


def get_genie_agent() -> GenieAgent:
    """Get global Genie agent instance"""
    global _genie_agent
    if _genie_agent is None:
        _genie_agent = GenieAgent()
    return _genie_agent
