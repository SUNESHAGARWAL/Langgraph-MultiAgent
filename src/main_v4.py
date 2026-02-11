"""
Enhanced Multi-Agent CLI v4.0
============================

Run the complete enhanced multi-agent system with:
- Schema understanding
- Query planning
- Clean Genie execution
- Validation
- Agentic RAG
- Human-in-loop

Usage:
    python -m src.main_v4

Author: Claude Code
Version: 4.0.0
Date: 2026-02-11
"""

import uuid
from langchain_core.messages import HumanMessage
from src.agent_v4_enhanced import get_enhanced_agent
from src.utils.logging import logger


def print_banner():
    """Print system banner"""
    print("=" * 80)
    print("Enhanced Multi-Agent Orchestrator v4.0")
    print("=" * 80)
    print()
    print("✨ INTELLIGENT MULTI-AGENT SYSTEM")
    print()
    print("Architecture:")
    print("  1. Schema Agent: Understands Unity Catalog tables/columns")
    print("  2. Query Planner: Decomposes complex questions")
    print("  3. Genie Executor: Sends clean SQL queries (not chat history!)")
    print("  4. RAG Agent: Provides document context")
    print("  5. Validation: Checks if results answer the question")
    print("  6. Synthesis: Creates comprehensive final answer")
    print()
    print("Features:")
    print("  ✅ Automatic schema analysis")
    print("  ✅ Complex question decomposition")
    print("  ✅ Clean query formatting for Genie")
    print("  ✅ Intelligent RAG integration (Genie+RAG, Genie, or RAG)")
    print("  ✅ Result validation")
    print("  ✅ Human-in-loop for clarification")
    print("  ✅ Conversation memory")
    print()


def main():
    """Main CLI loop"""

    print_banner()

    # Initialize enhanced agent
    try:
        print("🚀 Initializing enhanced multi-agent system...")
        agent = get_enhanced_agent()
        print("✅ System initialized successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        logger.error(f"Initialization failed: {e}")
        return

    # Interactive loop
    print("💬 Ask me anything! (type 'exit' to quit)")
    print()

    # Generate thread ID for conversation memory
    thread_id = str(uuid.uuid4())

    try:
        while True:
            # Get user input
            question = input("🤔 You: ").strip()

            if not question:
                continue

            if question.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Invoke enhanced multi-agent system
            print("\n🤖 Processing...\n")

            try:
                # Create input state
                input_state = {
                    "messages": [HumanMessage(content=question)],
                    "original_question": "",
                    "relevant_tables": [],
                    "relevant_columns": {},
                    "schema_confidence": 0.0,
                    "is_answerable": False,
                    "missing_information": [],
                    "query_plan": [],
                    "needs_decomposition": False,
                    "formatted_queries": [],
                    "needs_sql": False,
                    "needs_rag": False,
                    "execution_mode": "",
                    "genie_results": [],
                    "rag_results": [],
                    "validation_status": "",
                    "validation_feedback": "",
                    "next_agent": "",
                    "iterations": 0,
                    "final_answer": ""
                }

                # Invoke with conversation memory
                result = agent.invoke(
                    input_state,
                    config={"configurable": {"thread_id": thread_id}}
                )

                # Extract final answer
                final_answer = result.get("final_answer", "")

                if not final_answer:
                    # Fallback to last message
                    messages = result.get("messages", [])
                    if messages:
                        final_answer = messages[-1].content

                # Display results
                print("✨ Answer:")
                print(final_answer)
                print()

                # Show execution details
                iterations = result.get("iterations", 0)
                if iterations > 1:
                    print(f"⚙️  Completed in {iterations} iterations")

                # Show which agents were used
                execution_mode = result.get("execution_mode", "")
                if execution_mode:
                    print(f"📊 Execution: {execution_mode}")

                # Show schema info
                relevant_tables = result.get("relevant_tables", [])
                if relevant_tables:
                    print(f"🗄️  Tables queried: {', '.join(relevant_tables)}")

                print()

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                logger.error(f"Query failed: {e}", exc_info=True)
                print()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
