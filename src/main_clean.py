"""
Enhanced Multi-Agent CLI v4.0 - CLEAN
====================================

Run the clean enhanced multi-agent system.

Usage:
    python -m src.main_clean

Author: Claude Code
Version: 4.0.0-clean
Date: 2026-02-11
"""

import uuid
from langchain_core.messages import HumanMessage
from src.agent_v4_clean import get_agent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def print_banner():
    """Print system banner"""
    print("=" * 80)
    print("Enhanced Multi-Agent Orchestrator v4.0 - CLEAN")
    print("=" * 80)
    print()
    print("✨ INTELLIGENT MULTI-AGENT SYSTEM")
    print()
    print("Features:")
    print("  ✅ Reads Unity Catalog tables, columns, and comments")
    print("  ✅ Analyzes schema to understand available data")
    print("  ✅ Plans and formats clean SQL queries")
    print("  ✅ Sends formatted questions to Genie (not chat history!)")
    print("  ✅ Validates results and self-corrects")
    print("  ✅ Conditional RAG integration")
    print()


def main():
    """Main CLI loop"""

    print_banner()

    # Initialize agent
    try:
        print("🚀 Initializing system and reading Unity Catalog schemas...")
        agent = get_agent()
        print("✅ System initialized successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        logger.error(f"Initialization failed: {e}")
        return

    # Interactive loop
    print("💬 Ask me anything! (type 'exit' to quit)")
    print()

    thread_id = str(uuid.uuid4())

    try:
        while True:
            question = input("🤔 You: ").strip()

            if not question:
                continue

            if question.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break

            print("\n🤖 Processing...\n")

            try:
                # Create input state
                input_state = {
                    "messages": [HumanMessage(content=question)],
                    "original_question": "",
                    "schema_info": {},
                    "relevant_tables": [],
                    "is_answerable": False,
                    "missing_information": [],
                    "formatted_queries": [],
                    "execution_mode": "",
                    "genie_results": [],
                    "rag_results": [],
                    "is_complete": False,
                    "validation_feedback": "",
                    "next_agent": "",
                    "iterations": 0,
                    "final_answer": ""
                }

                # Invoke with memory
                result = agent.invoke(
                    input_state,
                    config={"configurable": {"thread_id": thread_id}}
                )

                # Extract answer
                final_answer = result.get("final_answer", "")
                if not final_answer:
                    messages = result.get("messages", [])
                    if messages:
                        final_answer = messages[-1].content

                # Display
                print("✨ Answer:")
                print(final_answer)
                print()

                # Show details
                iterations = result.get("iterations", 0)
                if iterations > 1:
                    print(f"⚙️  Completed in {iterations} iterations")

                execution_mode = result.get("execution_mode", "")
                if execution_mode:
                    print(f"📊 Mode: {execution_mode}")

                relevant_tables = result.get("relevant_tables", [])
                if relevant_tables:
                    print(f"🗄️  Tables: {', '.join(relevant_tables)}")

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
