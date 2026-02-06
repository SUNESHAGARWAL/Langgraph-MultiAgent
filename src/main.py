"""
Main entry point for Multi-Agent Orchestrator System

Uses LangChain Deep Agents with:
- Databricks Genie for SQL queries
- Vector Search for RAG
- TodoListMiddleware for planning
- Azure Blob Storage for document monitoring
"""

import uuid
import time
from typing import Dict, Any, Optional

from src.core.config import config
from src.agent import get_orchestrator
from src.services.blob_monitor import get_blob_monitor
from src.services.mlflow_tracker import get_mlflow_tracker
from src.utils.logging import get_logger, set_session_id, set_request_id

logger = get_logger(__name__)


class MultiAgentOrchestrator:
    """
    Multi-agent orchestrator using LangChain Deep Agents.

    Provides a simple interface for:
    - Querying data via natural language (Genie)
    - Retrieving documents (RAG)
    - Task planning and execution (TodoListMiddleware)
    """

    def __init__(self, auto_start_monitoring: bool = True):
        """
        Initialize the multi-agent orchestrator.

        Args:
            auto_start_monitoring: Whether to start Azure Blob monitoring for RAG
        """
        logger.info("Initializing Multi-Agent Orchestrator")

        # Get the Deep Agent
        self.agent = get_orchestrator()

        # MLflow tracking
        self.tracker = get_mlflow_tracker()

        # Start Azure Blob monitoring for RAG documents
        if auto_start_monitoring and config.rag.auto_process:
            try:
                self.blob_monitor = get_blob_monitor()
                self.blob_monitor.start()
                logger.info("Started Azure Blob Storage monitoring for RAG")
            except Exception as e:
                logger.warning(f"Failed to start blob monitoring: {e}")
                self.blob_monitor = None

        logger.info("Multi-Agent Orchestrator initialized successfully")

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Query the multi-agent system.

        Args:
            question: Natural language question
            session_id: Optional session ID for conversation tracking
            stream: Whether to stream the response (not yet implemented)

        Returns:
            Dict containing:
            - success: bool
            - answer: str (the response)
            - todos: list (task breakdown if applicable)
            - latency: float (seconds)
            - sources: list (data sources used)
            - session_id: str
            - request_id: str
        """
        # Generate IDs
        if session_id is None:
            session_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        set_session_id(session_id)
        set_request_id(request_id)

        start_time = time.time()

        logger.info(
            f"Processing query",
            question=question,
            session_id=session_id,
            request_id=request_id,
        )

        # Start MLflow run
        run_name = f"query_{request_id[:8]}"
        with self.tracker.start_run(run_name=run_name):
            self.tracker.log_params({"question": question, "session_id": session_id})

            try:
                # Invoke the agent
                result = self.agent.invoke({
                    "messages": [{"role": "user", "content": question}]
                })

                # Extract response
                # Note: Actual response format depends on LangChain agent implementation
                # Adjust based on actual structure
                answer = result.get("output", str(result))
                todos = result.get("todos", [])

                latency = time.time() - start_time

                # Log metrics
                self.tracker.log_metrics({
                    "latency_seconds": latency,
                    "success": 1,
                })

                logger.info(
                    f"Query succeeded",
                    latency=latency,
                    session_id=session_id,
                    request_id=request_id,
                )

                return {
                    "success": True,
                    "answer": answer,
                    "todos": todos,
                    "latency": latency,
                    "sources": self._extract_sources(result),
                    "session_id": session_id,
                    "request_id": request_id,
                }

            except Exception as e:
                latency = time.time() - start_time

                self.tracker.log_metrics({
                    "latency_seconds": latency,
                    "success": 0,
                })

                logger.error(
                    f"Query failed",
                    error=str(e),
                    latency=latency,
                    session_id=session_id,
                    request_id=request_id,
                )

                return {
                    "success": False,
                    "error": str(e),
                    "latency": latency,
                    "session_id": session_id,
                    "request_id": request_id,
                }

    def _extract_sources(self, result: Dict[str, Any]) -> list:
        """Extract data sources used from agent result"""
        sources = []

        # Check if Genie was used
        if "genie" in str(result).lower() or "sql" in str(result).lower():
            sources.append("Databricks Genie (SQL)")

        # Check if documents were retrieved
        if "document" in str(result).lower() or "search" in str(result).lower():
            sources.append("RAG Documents")

        return sources if sources else ["Agent"]

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'blob_monitor') and self.blob_monitor:
            try:
                self.blob_monitor.stop()
                logger.info("Stopped blob monitoring")
            except Exception as e:
                logger.warning(f"Error stopping blob monitor: {e}")


def main():
    """
    CLI entry point for interactive queries.
    """
    print("=" * 80)
    print("Multi-Agent Orchestrator v1.0.0 (LangChain Deep Agents)")
    print("=" * 80)
    print()

    # Initialize orchestrator
    try:
        orchestrator = MultiAgentOrchestrator(auto_start_monitoring=True)
        print("✅ System initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize system: {e}")
        return

    # Interactive CLI
    print("💬 Ready for questions! (type 'exit' to quit)")
    print()

    try:
        while True:
            # Get user input
            question = input("🤔 You: ").strip()

            if not question:
                continue

            if question.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Process query
            print("\n🤖 Processing...\n")

            result = orchestrator.query(question=question)

            if result["success"]:
                print("✨ Answer:")
                print(result["answer"])
                print()

                if result.get("todos"):
                    print("📋 Task Breakdown:")
                    for i, todo in enumerate(result["todos"], 1):
                        print(f"  {i}. {todo}")
                    print()

                print(f"📚 Sources: {', '.join(result['sources'])}")
                print(f"⏱️  Latency: {result['latency']:.2f}s")
            else:
                print(f"❌ Error: {result['error']}")

            print()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    finally:
        orchestrator.cleanup()


if __name__ == "__main__":
    main()
