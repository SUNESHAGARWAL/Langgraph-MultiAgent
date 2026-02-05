"""
Main entry point for Multi-Agent Orchestrator System.
"""

import uuid
import time
from typing import Dict, Any, List, Optional

from src.core.config import config
from src.core.state import create_initial_state
from src.agents.orchestrator import get_orchestrator
from src.agents.synthesis_agent import get_synthesis_agent
from src.agents.human_loop import get_human_loop_agent
from src.agents.rag_agent import get_rag_agent
from src.agents.table_understanding import get_table_understanding_agent
from src.services.mlflow_tracker import get_mlflow_tracker
from src.utils.logging import get_logger, set_session_id, set_request_id

logger = get_logger(__name__)


class MultiAgentOrchestrator:
    """
    Main orchestrator for the multi-agent system.
    Provides a simple interface for querying the system.
    """

    def __init__(self, auto_start_rag: bool = True):
        """
        Initialize the multi-agent orchestrator.

        Args:
            auto_start_rag: Whether to automatically start RAG file monitoring
        """
        logger.info("Initializing Multi-Agent Orchestrator")

        # Initialize all agents
        self.orchestrator = get_orchestrator()
        self.synthesis_agent = get_synthesis_agent()
        self.human_loop = get_human_loop_agent()
        self.rag_agent = get_rag_agent()
        self.table_agent = get_table_understanding_agent()
        self.tracker = get_mlflow_tracker()

        # Start RAG monitoring if enabled
        if auto_start_rag and config.rag.auto_process:
            try:
                self.rag_agent.start_monitoring()
                logger.info("Started RAG file monitoring")
            except Exception as e:
                logger.warning(f"Failed to start RAG monitoring: {e}")

        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}

        logger.info("Multi-Agent Orchestrator initialized successfully")

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user query through the multi-agent system.

        Args:
            question: User question
            session_id: Optional session ID (will create new if not provided)
            conversation_history: Optional conversation history

        Returns:
            Response dictionary with answer and metadata
        """
        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())

        request_id = str(uuid.uuid4())

        # Set context for logging
        set_session_id(session_id)
        set_request_id(request_id)

        logger.info(
            "Processing query",
            question=question,
            session_id=session_id,
            request_id=request_id,
        )

        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation_history": conversation_history or [],
                "created_at": time.time(),
            }

        session = self.sessions[session_id]

        # Start MLflow run
        with self.tracker.start_run(
            run_name=f"query_{request_id[:8]}",
            tags={
                "session_id": session_id,
                "request_id": request_id,
            },
        ):
            try:
                # Log parameters
                self.tracker.log_params({
                    "question": question[:100],  # Truncate for MLflow
                    "session_id": session_id,
                    "has_history": len(session["conversation_history"]) > 0,
                })

                # Orchestrate
                start_time = time.time()

                orchestration_result = self.orchestrator.orchestrate(
                    question=question,
                    conversation_history=session["conversation_history"],
                    context={"session_id": session_id},
                )

                # Check if needs clarification
                if orchestration_result.get("needs_clarification"):
                    clarification_q = orchestration_result["clarification_question"]

                    logger.info("Needs clarification from user")

                    return {
                        "success": False,
                        "needs_clarification": True,
                        "clarification_question": clarification_q,
                        "session_id": session_id,
                        "request_id": request_id,
                    }

                # Synthesize final answer
                if orchestration_result["success"]:
                    synthesis_result = self.synthesis_agent.synthesize(
                        question=question,
                        agent_results=orchestration_result.get("result", {}),
                        execution_log=orchestration_result.get("execution_log", []),
                        conversation_history=session["conversation_history"],
                    )

                    latency = time.time() - start_time

                    # Log metrics
                    self.tracker.log_metrics({
                        "latency_seconds": latency,
                        "iterations": orchestration_result.get("iterations", 0),
                        "success": 1.0,
                    })

                    # Update conversation history
                    session["conversation_history"].append({
                        "role": "user",
                        "content": question,
                    })
                    session["conversation_history"].append({
                        "role": "assistant",
                        "content": synthesis_result["answer"],
                    })

                    logger.info(
                        "Query completed successfully",
                        latency=latency,
                        iterations=orchestration_result.get("iterations"),
                    )

                    return {
                        "success": True,
                        "answer": synthesis_result["answer"],
                        "sources": synthesis_result.get("sources_used", []),
                        "plan": orchestration_result.get("plan"),
                        "execution_log": orchestration_result.get("execution_log"),
                        "iterations": orchestration_result.get("iterations"),
                        "latency": latency,
                        "session_id": session_id,
                        "request_id": request_id,
                    }

                else:
                    # Orchestration failed
                    error_msg = orchestration_result.get("error", "Unknown error")

                    logger.error(f"Orchestration failed: {error_msg}")

                    self.tracker.log_metrics({
                        "success": 0.0,
                    })

                    return {
                        "success": False,
                        "error": error_msg,
                        "execution_log": orchestration_result.get("execution_log"),
                        "session_id": session_id,
                        "request_id": request_id,
                    }

            except Exception as e:
                logger.error(f"Query processing failed: {e}", exc_info=True)

                self.tracker.log_metrics({
                    "success": 0.0,
                    "error": 1.0,
                })

                return {
                    "success": False,
                    "error": str(e),
                    "session_id": session_id,
                    "request_id": request_id,
                }

    def provide_clarification(
        self,
        session_id: str,
        clarification: str,
    ) -> Dict[str, Any]:
        """
        Provide clarification to a previous query that needed more information.

        Args:
            session_id: Session ID
            clarification: User's clarification

        Returns:
            Response dictionary
        """
        logger.info(
            "Received clarification",
            session_id=session_id,
            clarification=clarification,
        )

        # Get the original question from session
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
            }

        # Re-query with clarification added to context
        session = self.sessions[session_id]
        last_user_msg = None

        for msg in reversed(session["conversation_history"]):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg is None:
            return {
                "success": False,
                "error": "No previous question found in session",
            }

        # Append clarification to conversation history
        session["conversation_history"].append({
            "role": "user",
            "content": f"Clarification: {clarification}",
        })

        # Re-run query with updated history
        combined_question = f"{last_user_msg}\n\nAdditional context: {clarification}"

        return self.query(
            question=combined_question,
            session_id=session_id,
            conversation_history=session["conversation_history"],
        )

    def analyze_tables(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze all Unity Catalog tables.

        Args:
            force_refresh: Force re-analysis

        Returns:
            Analysis summary
        """
        logger.info("Starting table analysis", force_refresh=force_refresh)

        result = self.table_agent.analyze_all_tables(force_refresh=force_refresh)

        logger.info(
            "Table analysis complete",
            successful=len(result.get("analyzed_tables", [])),
            failed=len(result.get("failed_tables", [])),
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            "rag_stats": self.rag_agent.get_stats(),
            "active_sessions": len(self.sessions),
            "app_config": {
                "name": config.app.name,
                "version": config.app.version,
                "environment": config.app.environment,
            },
        }

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up orchestrator")

        # Stop RAG monitoring
        self.rag_agent.stop_monitoring()

        logger.info("Cleanup complete")


def main():
    """Simple CLI interface"""
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   Multi-Agent Orchestrator v{config.app.version}                     ║
║   Environment: {config.app.environment}                             ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Initialize orchestrator
    orchestrator = MultiAgentOrchestrator(auto_start_rag=True)

    # Analyze tables if configured
    if config.databricks.unity_tables:
        print("\n📊 Analyzing Unity Catalog tables...")
        result = orchestrator.analyze_tables()
        print(f"✓ Analyzed {len(result['analyzed_tables'])} tables")

    print("\n💬 Ready for questions! (type 'exit' to quit)\n")

    session_id = str(uuid.uuid4())

    try:
        while True:
            question = input("\n🤔 You: ").strip()

            if not question:
                continue

            if question.lower() in ["exit", "quit", "bye"]:
                print("\n👋 Goodbye!")
                break

            if question.lower() == "stats":
                stats = orchestrator.get_stats()
                print(f"\n📊 Stats: {stats}")
                continue

            # Process query
            print("\n🤖 Processing...")

            result = orchestrator.query(question, session_id=session_id)

            if result.get("needs_clarification"):
                print(f"\n🤔 {result['clarification_question']}")

                clarification = input("\n🤔 You: ").strip()

                if clarification:
                    result = orchestrator.provide_clarification(
                        session_id=session_id,
                        clarification=clarification,
                    )

            if result["success"]:
                print(f"\n✨ Answer:\n{result['answer']}")

                if result.get("sources"):
                    print(f"\n📚 Sources: {', '.join(result['sources'])}")

                print(f"\n⏱️ Latency: {result.get('latency', 0):.2f}s")

            else:
                print(f"\n❌ Error: {result.get('error')}")

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")

    finally:
        orchestrator.cleanup()


if __name__ == "__main__":
    main()
