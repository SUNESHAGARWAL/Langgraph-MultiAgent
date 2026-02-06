"""
Main entry point for Multi-Agent Orchestrator

Simple CLI using LangGraph agent with Databricks Genie and RAG.
"""

from langchain_core.messages import HumanMessage
from src.agent import get_agent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """
    Simple CLI for interacting with the agent.
    """
    print("=" * 80)
    print("Multi-Agent Orchestrator (LangGraph + Databricks Genie)")
    print("=" * 80)
    print()

    # Initialize agent
    try:
        agent = get_agent()
        print("✅ Agent initialized successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        logger.error(f"Agent initialization failed: {e}")
        return

    # Interactive loop
    print("💬 Ask me anything! (type 'exit' to quit)")
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

            # Invoke agent
            print()
            try:
                result = agent.invoke({"messages": [HumanMessage(content=question)]})

                # Extract answer
                messages = result.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    answer = last_message.content if hasattr(last_message, 'content') else str(last_message)

                    print("✨ Agent:")
                    print(answer)
                else:
                    print("⚠️  No response from agent")

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                logger.error(f"Query failed: {e}")

            print()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error(f"Unexpected error in main loop: {e}")


if __name__ == "__main__":
    main()
