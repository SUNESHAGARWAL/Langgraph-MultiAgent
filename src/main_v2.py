"""
Main entry point for Multi-Agent Orchestrator System (Version 2 with LangGraph).
This version uses the proper LangGraph StateGraph implementation.
"""

import uuid
import time
from typing import Dict, Any, List, Optional

from src.core.config import config
from src.core.graph import get_multi_agent_graph
from src.agents.rag_agent import get_rag_agent
from src.agents.table_understanding import get_table_understanding_agent
from src.services.mlflow_tracker import get_mlflow_tracker
from src.utils.logging import get_logger, set_session_id, set_request_id

logger = get_logger(__name__)


class MultiAgentOrchestratorV2:
    """
    Main orchestrator for the multi-agent system using LangGraph StateGraph.
    """

    def __init__(self, auto_start_rag: bool = True):
        """
        Initialize the multi-agent orchestrator.

        Args:
            auto_start_rag: Whether to automatically start RAG file monitoring
        """
        logger.info("Initializing Multi-Agent Orchestrator V2 (LangGraph)")

        # Initialize graph
        self.graph = get_multi_agent_graph()

        # Initialize supporting agents
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

        logger.info("Multi-Agent Orchestrator V2 initialized successfully")

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user query through the multi-agent system using LangGraph.

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
            "Processing query (LangGraph V2)",
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
            run_name=f"query_v2_{request_id[:8]}",
            tags={
                "session_id": session_id,
                "request_id": request_id,
                "version": "v2_langgraph",
            },
        ):
            try:
                # Log parameters
                self.tracker.log_params({
                    "question": question[:100],
                    "session_id": session_id,
                    "has_history": len(session["conversation_history"]) > 0,
                    "version": "v2_langgraph",
                })

                # Run LangGraph
                start_time = time.time()

                final_state = self.graph.invoke(
                    question=question,
                    session_id=session_id,
                    conversation_history=session["conversation_history"],
                )

                latency = time.time() - start_time

                # Check if needs clarification
                if final_state.get("needs_clarification"):
                    clarification_q = final_state["clarification_question"]

                    logger.info("Needs clarification from user")

                    return {
                        "success": False,
                        "needs_clarification": True,
                        "clarification_question": clarification_q,
                        "session_id": session_id,
                        "request_id": request_id,
                    }

                # Check if successful
                if final_state["success"] and final_state["final_answer"]:
                    answer = final_state["final_answer"]
                    synthesis_result = final_state.get("synthesis_result", {})

                    # Log metrics
                    self.tracker.log_metrics({
                        "latency_seconds": latency,
                        "iterations": final_state["iteration_count"],
                        "cache_hits": final_state["cache_hits"],
                        "cache_misses": final_state["cache_misses"],
                        "success": 1.0,
                    })

                    # Update conversation history
                    session["conversation_history"].append({
                        "role": "user",
                        "content": question,
                    })
                    session["conversation_history"].append({
                        "role": "assistant",
                        "content": answer,
                    })

                    logger.info(
                        "Query completed successfully",
                        latency=latency,
                        iterations=final_state["iteration_count"],
                    )

                    return {
                        "success": True,
                        "answer": answer,
                        "sources": synthesis_result.get("sources_used", []),
                        "execution_log": final_state.get("execution_log", []),
                        "iterations": final_state["iteration_count"],
                        "cache_hits": final_state["cache_hits"],
                        "cache_misses": final_state["cache_misses"],
                        "latency": latency,
                        "session_id": session_id,
                        "request_id": request_id,
                    }

                else:
                    # Execution failed
                    errors = final_state.get("errors", [])
                    error_msg = "; ".join(errors) if errors else "Unknown error"

                    logger.error(f"Query execution failed: {error_msg}")

                    self.tracker.log_metrics({
                        "success": 0.0,
                        "iterations": final_state["iteration_count"],
                    })

                    return {
                        "success": False,
                        "error": error_msg,
                        "execution_log": final_state.get("execution_log", []),
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
        Provide clarification to a previous query.

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

        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
            }

        # Re-query with clarification
        session = self.sessions[session_id]
        last_user_msg = None

        for msg in reversed(session["conversation_history"]):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg is None:
            return {
                "success": False,
                "error": "No previous question found",
            }

        # Append clarification
        session["conversation_history"].append({
            "role": "user",
            "content": f"Clarification: {clarification}",
        })

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
            "version": "v2_langgraph",
        }

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up orchestrator V2")
        self.rag_agent.stop_monitoring()
        logger.info("Cleanup complete")


def main():
    """Simple CLI interface using LangGraph V2"""
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   Multi-Agent Orchestrator v{config.app.version} (LangGraph V2)          ║
║   Environment: {config.app.environment}                             ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Initialize orchestrator
    orchestrator = MultiAgentOrchestratorV2(auto_start_rag=True)

    # Analyze tables if configured
    if config.databricks.unity_tables:
        print("\n📊 Analyzing Unity Catalog tables...")
        result = orchestrator.analyze_tables()
        print(f"✓ Analyzed {len(result['analyzed_tables'])} tables")

    print("\n💬 Ready for questions! (type 'exit' to quit)")
    print("🆕 Using LangGraph StateGraph implementation\n")

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
            print("\n🤖 Processing with LangGraph...")

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
                print(f"🔄 Iterations: {result.get('iterations', 0)}")
                print(f"📊 Cache: {result.get('cache_hits', 0)} hits, {result.get('cache_misses', 0)} misses")

            else:
                print(f"\n❌ Error: {result.get('error')}")

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")

    finally:
        orchestrator.cleanup()


if __name__ == "__main__":
    main()
