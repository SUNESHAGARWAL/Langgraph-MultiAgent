"""
Simplified Multi-Agent CLI v5.0
================================

Clean, streamlined multi-agent system with:
- Unity Catalog schema reading
- Semantic column matching
- Clean Genie query execution
- Conversation memory
- NO validation loops!

Usage:
    python -m src.main_simple

Author: Claude Code
Version: 5.0.0-simple
Date: 2026-02-11
"""

import uuid
from langchain_core.messages import HumanMessage
from src.agent_simple import get_agent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def print_banner():
    """Print system banner"""
    print("=" * 80)
    print("Simplified Multi-Agent Orchestrator v5.0")
    print("=" * 80)
    print()
    print("✨ CLEAN & SIMPLE ARCHITECTURE")
    print()
    print("Features:")
    print("  ✅ Reads Unity Catalog schemas")
    print("  ✅ Semantic column matching (LLM-based)")
    print("  ✅ Clean query formatting for Genie")
    print("  ✅ No validation loops!")
    print("  ✅ Conversation memory")
    print()
    print("Flow:")
    print("  User Question → Schema Analysis → Query Planning → Genie → Synthesis")
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
        logger.error(f"Initialization failed: {e}", exc_info=True)
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
                # Create input state with new message
                # LangGraph checkpointer preserves conversation state
                input_state = {
                    "messages": [HumanMessage(content=question)],
                    "next_agent": "",
                    "iterations": 0,
                    "final_answer": "",
                    "schema_info": "",
                    "is_answerable": False,
                    "formatted_query": ""
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
                if iterations > 0:
                    print(f"⚙️  Completed in {iterations} iteration(s)")

                is_answerable = result.get("is_answerable")
                if is_answerable is not None:
                    print(f"📊 Answerable: {is_answerable}")

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
