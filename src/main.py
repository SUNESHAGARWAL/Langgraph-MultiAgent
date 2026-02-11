"""
Main entry point for Multi-Agent Orchestrator

Uses LangGraph Multi-Agent Supervisor pattern with:
- Supervisor Agent: Routes to specialists
- Specialist Agents: Genie (SQL), RAG (docs)
- Synthesis Agent: Combines results
- Human-in-Loop: Asks for clarification
"""

import uuid
from langchain_core.messages import HumanMessage
from src.agent import get_agent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """
    Simple CLI for multi-agent orchestrator.
    """
    print("=" * 80)
    print("Multi-Agent Orchestrator (Supervisor + Specialists)")
    print("=" * 80)
    print()

    # Initialize agent graph
    try:
        agent = get_agent()
        print("✅ Multi-agent system initialized")
        print()
        print("Architecture:")
        print("  - Supervisor: Routes to specialists")
        print("  - SQL Specialist: Queries Unity Catalog via Genie")
        print("  - Document Specialist: Searches uploaded documents")
        print("  - Synthesis: Combines results")
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

            # Invoke multi-agent system
            print("\n🤖 Processing...\n")

            try:
                # Add new message to existing conversation
                # LangGraph will load previous state from checkpointer automatically
                input_state = {
                    "messages": [HumanMessage(content=question)],
                }

                # Invoke with conversation memory
                # Note: iterations and other state preserved by checkpointer
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

                print("✨ Answer:")
                print(final_answer)
                print()

                # Show iterations
                iterations = result.get("iterations", 0)
                if iterations > 1:
                    print(f"⚙️  Solved in {iterations} iterations")
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
