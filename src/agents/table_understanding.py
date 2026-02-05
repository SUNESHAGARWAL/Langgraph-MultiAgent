"""
Table Understanding Agent for EDA and metadata extraction from Unity Catalog tables.
Stores table/column information in vector store for semantic search.
"""

from typing import Dict, Any, List, Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from src.core.config import config
from src.services.vector_store import get_vector_store
from src.services.storage import get_storage_service
from src.services.mlflow_tracker import track_agent
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class TableUnderstandingAgent:
    """
    Agent for understanding Unity Catalog tables through EDA and metadata extraction.
    Builds a semantic index of tables and columns for intelligent routing.
    """

    def __init__(self):
        self.client = self._initialize_client()
        self.catalog = config.databricks.unity_catalog
        self.schema = config.databricks.unity_schema
        self.tables = config.databricks.unity_tables

        self.vector_store = get_vector_store("table_metadata")
        self.storage = get_storage_service()

        logger.info(
            f"Initialized TableUnderstandingAgent",
            catalog=self.catalog,
            schema=self.schema,
            num_tables=len(self.tables),
        )

    def _initialize_client(self) -> WorkspaceClient:
        """Initialize Databricks WorkspaceClient"""
        try:
            client = WorkspaceClient(
                host=config.databricks.host,
                token=config.databricks.token,
            )
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Databricks client: {e}")
            raise

    @trace_function("analyze_all_tables")
    def analyze_all_tables(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze all configured tables and build vector index.

        Args:
            force_refresh: Force re-analysis even if cached

        Returns:
            Summary of analysis
        """
        results = {
            "analyzed_tables": [],
            "failed_tables": [],
            "total_tables": len(self.tables),
        }

        for table in self.tables:
            try:
                logger.info(f"Analyzing table: {table}")
                analysis = self.analyze_table(table, force_refresh=force_refresh)

                if analysis["success"]:
                    results["analyzed_tables"].append(table)
                else:
                    results["failed_tables"].append(table)

            except Exception as e:
                logger.error(f"Failed to analyze table {table}: {e}")
                results["failed_tables"].append(table)

        logger.info(
            f"Table analysis complete",
            successful=len(results["analyzed_tables"]),
            failed=len(results["failed_tables"]),
        )

        return results

    @trace_function("analyze_table")
    @track_agent("table_understanding_agent")
    def analyze_table(
        self,
        table_name: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Analyze a single table: schema, statistics, sample data.

        Args:
            table_name: Table name
            force_refresh: Force re-analysis even if cached

        Returns:
            Table analysis results
        """
        full_table_name = config.get_full_table_name(table_name)

        # Check if analysis is cached
        if not force_refresh:
            cached_analysis = self.storage.load_eda_results(table_name)
            if cached_analysis:
                logger.info(f"Using cached analysis for {table_name}")
                return cached_analysis

        try:
            # Get table metadata
            metadata = self._get_table_metadata(full_table_name)

            # Get column statistics
            stats = self._get_column_statistics(full_table_name)

            # Get sample data
            sample_data = self._get_sample_data(full_table_name, limit=5)

            # Generate table description
            description = self._generate_table_description(
                table_name, metadata, stats, sample_data
            )

            analysis = {
                "success": True,
                "table_name": table_name,
                "full_table_name": full_table_name,
                "metadata": metadata,
                "statistics": stats,
                "sample_data": sample_data,
                "description": description,
            }

            # Store in blob storage
            self.storage.save_eda_results(table_name, analysis)

            # Add to vector store for semantic search
            self._index_table_metadata(table_name, description, metadata)

            logger.info(f"Completed analysis for {table_name}")

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze table {table_name}: {e}")
            return {
                "success": False,
                "table_name": table_name,
                "error": str(e),
            }

    def _get_table_metadata(self, full_table_name: str) -> Dict[str, Any]:
        """Get table schema and metadata"""
        query = f"DESCRIBE TABLE EXTENDED {full_table_name}"
        results = self._execute_sql(query)

        metadata = {
            "columns": [],
            "properties": {},
        }

        for row in results:
            col_name = row.get("col_name", "")
            data_type = row.get("data_type", "")
            comment = row.get("comment", "")

            if col_name and col_name.startswith("#"):
                # This is a property/metadata row
                continue
            elif col_name:
                metadata["columns"].append({
                    "name": col_name,
                    "type": data_type,
                    "comment": comment,
                })

        return metadata

    def _get_column_statistics(self, full_table_name: str) -> Dict[str, Any]:
        """Get column-level statistics"""
        try:
            # Get table statistics
            query = f"""
            SELECT
                COUNT(*) as row_count,
                COUNT(DISTINCT *) as distinct_count
            FROM {full_table_name}
            """
            results = self._execute_sql(query)

            stats = results[0] if results else {}

            return {
                "row_count": stats.get("row_count", 0),
                "distinct_count": stats.get("distinct_count", 0),
            }

        except Exception as e:
            logger.warning(f"Failed to get statistics: {e}")
            return {}

    def _get_sample_data(self, full_table_name: str, limit: int = 5) -> List[Dict]:
        """Get sample rows from table"""
        try:
            query = f"SELECT * FROM {full_table_name} LIMIT {limit}"
            return self._execute_sql(query)
        except Exception as e:
            logger.warning(f"Failed to get sample data: {e}")
            return []

    def _execute_sql(self, query: str, timeout: int = 30) -> List[Dict[str, Any]]:
        """
        Execute SQL query on Databricks.

        Args:
            query: SQL query
            timeout: Timeout in seconds

        Returns:
            List of result rows as dicts
        """
        try:
            # Execute statement
            statement = self.client.statement_execution.execute_statement(
                statement=query,
                warehouse_id=None,  # Will use default warehouse
                timeout=f"{timeout}s",
            )

            # Wait for completion
            while statement.status.state in [StatementState.PENDING, StatementState.RUNNING]:
                statement = self.client.statement_execution.get_statement(
                    statement_id=statement.statement_id
                )

            if statement.status.state != StatementState.SUCCEEDED:
                error = statement.status.error if hasattr(statement.status, "error") else "Unknown error"
                raise Exception(f"SQL execution failed: {error}")

            # Parse results
            results = []
            if statement.result and statement.result.data_array:
                columns = [col.name for col in statement.manifest.schema.columns]

                for row in statement.result.data_array:
                    row_dict = dict(zip(columns, row))
                    results.append(row_dict)

            return results

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise

    def _generate_table_description(
        self,
        table_name: str,
        metadata: Dict,
        stats: Dict,
        sample_data: List[Dict],
    ) -> str:
        """Generate a human-readable description of the table"""
        description_parts = [
            f"Table: {table_name}",
            f"Columns: {', '.join([col['name'] for col in metadata.get('columns', [])])}",
        ]

        if stats.get("row_count"):
            description_parts.append(f"Row count: {stats['row_count']}")

        # Add column details
        column_details = []
        for col in metadata.get("columns", []):
            detail = f"{col['name']} ({col['type']})"
            if col.get("comment"):
                detail += f" - {col['comment']}"
            column_details.append(detail)

        if column_details:
            description_parts.append("Column details: " + "; ".join(column_details))

        return ". ".join(description_parts)

    def _index_table_metadata(
        self,
        table_name: str,
        description: str,
        metadata: Dict,
    ):
        """Add table metadata to vector store for semantic search"""
        # Create searchable text
        searchable_text = f"{table_name}: {description}"

        # Add to vector store
        self.vector_store.add_documents(
            texts=[searchable_text],
            metadatas=[{
                "table_name": table_name,
                "type": "table_metadata",
            }],
            ids=[f"table_{table_name}"],
        )

        # Save vector store
        self.vector_store.save()

        logger.info(f"Indexed table metadata for {table_name}")

    @trace_function("search_tables")
    def search_tables(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant tables based on natural language query.

        Args:
            query: Natural language query
            top_k: Number of tables to return

        Returns:
            List of relevant tables with metadata
        """
        results = self.vector_store.similarity_search(query, k=top_k)

        tables = []
        for doc, similarity in results:
            table_name = doc["metadata"].get("table_name")
            if table_name:
                # Load full analysis
                analysis = self.storage.load_eda_results(table_name)
                if analysis:
                    tables.append({
                        "table_name": table_name,
                        "similarity": similarity,
                        "description": analysis.get("description"),
                        "columns": [col["name"] for col in analysis.get("metadata", {}).get("columns", [])],
                    })

        logger.info(f"Found {len(tables)} relevant tables for query")

        return tables

    @trace_function("get_table_suggestions")
    def get_table_suggestions(self) -> List[str]:
        """Get list of available tables with descriptions"""
        suggestions = []

        for table in self.tables:
            analysis = self.storage.load_eda_results(table)
            if analysis:
                suggestions.append(
                    f"- {table}: {analysis.get('description', 'No description')}"
                )
            else:
                suggestions.append(f"- {table}: (not yet analyzed)")

        return suggestions


# Global table understanding agent
_table_understanding_agent = None


def get_table_understanding_agent() -> TableUnderstandingAgent:
    """Get global table understanding agent"""
    global _table_understanding_agent
    if _table_understanding_agent is None:
        _table_understanding_agent = TableUnderstandingAgent()
    return _table_understanding_agent
