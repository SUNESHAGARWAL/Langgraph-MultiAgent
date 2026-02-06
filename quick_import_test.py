"""
Quick import test to verify critical modules load without errors.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("Testing critical imports...\n")

errors = []

# Test 1: LangChain Core
try:
    from langchain_core.documents import Document
    print("✅ langchain_core.documents.Document")
except Exception as e:
    print(f"❌ langchain_core.documents.Document: {e}")
    errors.append(("langchain_core.documents", str(e)))

# Test 2: Configuration
try:
    from src.core.config import config
    print("✅ src.core.config")
    print(f"   - Azure OpenAI: {config.azure_openai.endpoint[:30]}...")
    print(f"   - Databricks: {config.databricks.host[:30]}...")
    print(f"   - Unity Tables: {config.databricks.unity_tables}")
    print(f"   - RAG Extensions: {config.rag.supported_extensions}")
except Exception as e:
    print(f"❌ src.core.config: {e}")
    errors.append(("src.core.config", str(e)))

# Test 3: Vector Store
try:
    from src.services.vector_store import get_vector_store
    print("✅ src.services.vector_store")
except Exception as e:
    print(f"❌ src.services.vector_store: {e}")
    errors.append(("src.services.vector_store", str(e)))

# Test 4: Agents
try:
    from src.agents.genie_agent import get_genie_agent
    print("✅ src.agents.genie_agent")
except Exception as e:
    print(f"❌ src.agents.genie_agent: {e}")
    errors.append(("src.agents.genie_agent", str(e)))

try:
    from src.agents.rag_agent import get_rag_agent
    print("✅ src.agents.rag_agent")
except Exception as e:
    print(f"❌ src.agents.rag_agent: {e}")
    errors.append(("src.agents.rag_agent", str(e)))

try:
    from src.agents.table_understanding import get_table_understanding_agent
    print("✅ src.agents.table_understanding")
except Exception as e:
    print(f"❌ src.agents.table_understanding: {e}")
    errors.append(("src.agents.table_understanding", str(e)))

try:
    from src.agents.synthesis_agent import get_synthesis_agent
    print("✅ src.agents.synthesis_agent")
except Exception as e:
    print(f"❌ src.agents.synthesis_agent: {e}")
    errors.append(("src.agents.synthesis_agent", str(e)))

try:
    from src.agents.orchestrator import get_orchestrator
    print("✅ src.agents.orchestrator")
except Exception as e:
    print(f"❌ src.agents.orchestrator: {e}")
    errors.append(("src.agents.orchestrator", str(e)))

# Test 5: Main Orchestrator
try:
    from src.main import MultiAgentOrchestrator
    print("✅ src.main.MultiAgentOrchestrator")
except Exception as e:
    print(f"❌ src.main.MultiAgentOrchestrator: {e}")
    errors.append(("src.main", str(e)))

print("\n" + "=" * 80)
if errors:
    print(f"❌ FAILED: {len(errors)} import errors found\n")
    for module, error in errors:
        print(f"   {module}: {error}")
    sys.exit(1)
else:
    print("✅ SUCCESS: All critical imports work correctly!")
    sys.exit(0)
