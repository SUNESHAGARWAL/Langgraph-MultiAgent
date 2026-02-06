"""
Quick import test to verify all modules load correctly.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("Testing imports...")

try:
    # Core
    print("✓ Testing core.config...")
    from src.core.config import config

    print("✓ Testing core.state...")
    from src.core.state import AgentState

    print("✓ Testing core.graph...")
    from src.core.graph import get_multi_agent_graph

    print("✓ Testing core.deep_agents_harness...")
    from src.core.deep_agents_harness import DeepAgentsHarness

    # Agents
    print("✓ Testing agents.orchestrator...")
    from src.agents.orchestrator import get_orchestrator_agent

    print("✓ Testing agents.genie_agent...")
    from src.agents.genie_agent import get_genie_agent

    print("✓ Testing agents.table_understanding...")
    from src.agents.table_understanding import get_table_understanding_agent

    print("✓ Testing agents.rag_agent...")
    from src.agents.rag_agent import get_rag_agent

    print("✓ Testing agents.agentic_rag...")
    from src.agents.agentic_rag import get_agentic_rag

    print("✓ Testing agents.synthesis_agent...")
    from src.agents.synthesis_agent import get_synthesis_agent

    print("✓ Testing agents.enhanced_synthesis...")
    from src.agents.enhanced_synthesis import get_enhanced_synthesis_agent

    print("✓ Testing agents.human_loop...")
    from src.agents.human_loop import get_human_loop_agent

    # Services
    print("✓ Testing services.caching...")
    from src.services.caching import get_cache

    print("✓ Testing services.vector_store...")
    from src.services.vector_store import get_vector_store

    print("✓ Testing services.storage...")
    from src.services.storage import get_blob_storage

    print("✓ Testing services.mlflow_tracker...")
    from src.services.mlflow_tracker import get_mlflow_tracker

    print("✓ Testing services.file_monitor...")
    from src.services.file_monitor import FileMonitor

    # Utils
    print("✓ Testing utils.logging...")
    from src.utils.logging import get_logger

    print("✓ Testing utils.embeddings...")
    from src.utils.embeddings import get_embedding_service

    print("✓ Testing utils.parsers...")
    from src.utils.parsers import DocumentParser

    print("\n✅ All imports successful!")

except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
