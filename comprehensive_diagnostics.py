"""
Comprehensive diagnostic script to verify all system components.
Checks imports, configuration, dependencies, and potential issues.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 80)
print("COMPREHENSIVE SYSTEM DIAGNOSTICS")
print("=" * 80)

# ============================================================================
# 1. CRITICAL IMPORTS CHECK
# ============================================================================
print("\n[1/8] CHECKING CRITICAL IMPORTS...")
print("-" * 80)

critical_imports = {
    "databricks.sdk": "Databricks SDK",
    "azure.storage.blob": "Azure Blob Storage",
    "pydantic": "Pydantic",
    "pydantic_settings": "Pydantic Settings",
}

import_errors = []
for module, name in critical_imports.items():
    try:
        __import__(module)
        print(f"✅ {name:30s} - OK")
    except ImportError as e:
        print(f"❌ {name:30s} - FAILED: {e}")
        import_errors.append((module, str(e)))

# ============================================================================
# 2. DATABRICKS SDK STRUCTURE CHECK
# ============================================================================
print("\n[2/8] CHECKING DATABRICKS SDK STRUCTURE...")
print("-" * 80)

try:
    from databricks import sdk
    print(f"✅ Databricks SDK version: {sdk.__version__}")

    from databricks.sdk import WorkspaceClient
    print(f"✅ WorkspaceClient available")

    from databricks.sdk.service import workspace
    print(f"✅ workspace service module available")

    # Check for Genie-related classes
    genie_classes = [attr for attr in dir(workspace) if 'genie' in attr.lower()]
    if genie_classes:
        print(f"✅ Genie-related classes found: {', '.join(genie_classes[:5])}")
    else:
        print(f"⚠️  No Genie-related classes found in workspace module")

except Exception as e:
    print(f"❌ Databricks SDK check failed: {e}")
    import_errors.append(("databricks.sdk", str(e)))

# ============================================================================
# 3. CONFIGURATION LOADING CHECK
# ============================================================================
print("\n[3/8] CHECKING CONFIGURATION LOADING...")
print("-" * 80)

config_errors = []
try:
    from src.core.config import config
    print(f"✅ Configuration loaded successfully")

    # Check critical config sections
    print(f"✅ Azure OpenAI endpoint: {config.azure_openai.endpoint[:30]}...")
    print(f"✅ Databricks host: {config.databricks.host[:30]}...")
    print(f"✅ Genie space ID: {config.databricks.genie_space_id}")
    print(f"✅ Unity Catalog tables: {len(config.databricks.unity_tables)} tables")

    # Check RAG config (this was causing Error 2)
    print(f"✅ RAG supported extensions: {config.rag.supported_extensions}")
    print(f"   Type: {type(config.rag.supported_extensions)}")

    # Check Azure Storage config
    cache_container, cache_prefix = config.azure_storage.get_cache_config()
    rag_container, rag_prefix = config.azure_storage.get_rag_config()
    eda_container, eda_prefix = config.azure_storage.get_eda_config()

    print(f"✅ Cache container: {cache_container}, prefix: '{cache_prefix}'")
    print(f"✅ RAG container: {rag_container}, prefix: '{rag_prefix}'")
    print(f"✅ EDA container: {eda_container}, prefix: '{eda_prefix}'")

except Exception as e:
    print(f"❌ Configuration loading failed: {e}")
    import traceback
    traceback.print_exc()
    config_errors.append(str(e))

# ============================================================================
# 4. AGENT IMPORTS CHECK
# ============================================================================
print("\n[4/8] CHECKING AGENT IMPORTS...")
print("-" * 80)

agent_modules = {
    "src.agents.orchestrator": "Orchestrator Agent",
    "src.agents.genie_agent": "Genie Agent",
    "src.agents.table_understanding": "Table Understanding Agent",
    "src.agents.rag_agent": "RAG Agent",
    "src.agents.synthesis_agent": "Synthesis Agent",
    "src.agents.human_loop": "Human Loop Agent",
}

agent_errors = []
for module, name in agent_modules.items():
    try:
        __import__(module)
        print(f"✅ {name:30s} - OK")
    except Exception as e:
        print(f"❌ {name:30s} - FAILED: {e}")
        agent_errors.append((module, str(e)))

# ============================================================================
# 5. SERVICE IMPORTS CHECK
# ============================================================================
print("\n[5/8] CHECKING SERVICE IMPORTS...")
print("-" * 80)

service_modules = {
    "src.services.caching": "Smart Cache Service",
    "src.services.vector_store": "Vector Store Service",
    "src.services.storage": "Azure Blob Storage Service",
    "src.services.blob_monitor": "Blob Monitor Service",
    "src.services.mlflow_tracker": "MLflow Tracker",
    "src.services.file_monitor": "File Monitor Service",
}

service_errors = []
for module, name in service_modules.items():
    try:
        __import__(module)
        print(f"✅ {name:30s} - OK")
    except Exception as e:
        print(f"❌ {name:30s} - FAILED: {e}")
        service_errors.append((module, str(e)))

# ============================================================================
# 6. UTILITY IMPORTS CHECK
# ============================================================================
print("\n[6/8] CHECKING UTILITY IMPORTS...")
print("-" * 80)

util_modules = {
    "src.utils.logging": "Logging Utilities",
    "src.utils.embeddings": "Embedding Service",
    "src.utils.parsers": "Document Parsers",
}

util_errors = []
for module, name in util_modules.items():
    try:
        __import__(module)
        print(f"✅ {name:30s} - OK")
    except Exception as e:
        print(f"❌ {name:30s} - FAILED: {e}")
        util_errors.append((module, str(e)))

# ============================================================================
# 7. FILE SYSTEM CHECK
# ============================================================================
print("\n[7/8] CHECKING FILE SYSTEM...")
print("-" * 80)

required_dirs = [
    "./data/vector_stores",
    "./data/sessions",
    "./data/cache",
    "./data/logs",
]

fs_issues = []
for directory in required_dirs:
    if os.path.exists(directory):
        print(f"✅ Directory exists: {directory}")
    else:
        print(f"⚠️  Directory missing (will be auto-created): {directory}")
        fs_issues.append(directory)

# Check .env file
if os.path.exists(".env"):
    print(f"✅ .env file exists")
else:
    print(f"❌ .env file missing - copy from .env.example")
    fs_issues.append(".env")

# ============================================================================
# 8. POTENTIAL ISSUES CHECK
# ============================================================================
print("\n[8/8] CHECKING FOR POTENTIAL ISSUES...")
print("-" * 80)

potential_issues = []

# Check for placeholder values in .env
try:
    from src.core.config import config

    if "your-resource" in config.azure_openai.endpoint:
        print(f"⚠️  Azure OpenAI endpoint contains placeholder value")
        potential_issues.append("Azure OpenAI endpoint not configured")

    if "your-api-key" in config.azure_openai.api_key:
        print(f"⚠️  Azure OpenAI API key contains placeholder value")
        potential_issues.append("Azure OpenAI API key not configured")

    if "your-workspace" in config.databricks.host:
        print(f"⚠️  Databricks host contains placeholder value")
        potential_issues.append("Databricks host not configured")

    if "your-account" in config.azure_storage.connection_string:
        print(f"⚠️  Azure Storage connection string contains placeholder value")
        potential_issues.append("Azure Storage connection not configured")

    if not potential_issues:
        print(f"✅ No placeholder values detected in configuration")

except Exception as e:
    print(f"❌ Could not check for placeholder values: {e}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)

total_errors = len(import_errors) + len(config_errors) + len(agent_errors) + len(service_errors) + len(util_errors)

if total_errors == 0 and len(potential_issues) == 0:
    print("\n🎉 ALL CHECKS PASSED!")
    print("✅ System is ready to use")
    sys.exit(0)
else:
    print(f"\n⚠️  FOUND {total_errors} ERRORS AND {len(potential_issues)} WARNINGS\n")

    if import_errors:
        print(f"❌ Import Errors ({len(import_errors)}):")
        for module, error in import_errors:
            print(f"   - {module}: {error}")

    if config_errors:
        print(f"\n❌ Configuration Errors ({len(config_errors)}):")
        for error in config_errors:
            print(f"   - {error}")

    if agent_errors:
        print(f"\n❌ Agent Import Errors ({len(agent_errors)}):")
        for module, error in agent_errors:
            print(f"   - {module}: {error}")

    if service_errors:
        print(f"\n❌ Service Import Errors ({len(service_errors)}):")
        for module, error in service_errors:
            print(f"   - {module}: {error}")

    if util_errors:
        print(f"\n❌ Utility Import Errors ({len(util_errors)}):")
        for module, error in util_errors:
            print(f"   - {module}: {error}")

    if potential_issues:
        print(f"\n⚠️  Configuration Warnings ({len(potential_issues)}):")
        for issue in potential_issues:
            print(f"   - {issue}")

    if fs_issues:
        print(f"\n⚠️  File System Warnings ({len(fs_issues)}):")
        for issue in fs_issues:
            print(f"   - {issue}")

    if total_errors > 0:
        print("\n❌ CRITICAL ERRORS DETECTED - System may not work correctly")
        sys.exit(1)
    else:
        print("\n⚠️  WARNINGS ONLY - System should work but may need configuration")
        sys.exit(0)
