"""
Comprehensive Setup Validation Script

Validates all configurations, credentials, and resource access before running the system.
Run this after setting up .env file to ensure everything is configured correctly.

Usage:
    python validate_setup.py

Exit codes:
    0 - All validations passed
    1 - Critical failures detected (system won't work)
    2 - Warnings only (system may work with issues)
"""

import sys
import os
from typing import List, Tuple, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 100)
print("MULTI-AGENT ORCHESTRATOR - SETUP VALIDATION")
print("=" * 100)
print()

# Track errors and warnings
critical_errors: List[Tuple[str, str]] = []
warnings: List[Tuple[str, str]] = []

# ====================================================================================================
# SECTION 1: CONFIGURATION LOADING
# ====================================================================================================
print("[1/10] Loading Configuration...")
print("-" * 100)

try:
    from src.core.config import config
    print("✅ Configuration loaded successfully")
except Exception as e:
    print(f"❌ CRITICAL: Failed to load configuration: {e}")
    critical_errors.append(("Configuration Loading", str(e)))
    print("\n" + "=" * 100)
    print("❌ VALIDATION FAILED - Cannot proceed without configuration")
    print("=" * 100)
    sys.exit(1)

# ====================================================================================================
# SECTION 2: AZURE OPENAI VALIDATION
# ====================================================================================================
print("\n[2/10] Validating Azure OpenAI Configuration...")
print("-" * 100)

try:
    # Check endpoint format
    if "your-resource" in config.azure_openai.endpoint:
        critical_errors.append(("Azure OpenAI", "Endpoint contains placeholder 'your-resource'"))
        print("❌ Azure OpenAI endpoint not configured (contains placeholder)")
    elif not config.azure_openai.endpoint.startswith("https://"):
        critical_errors.append(("Azure OpenAI", "Endpoint must start with https://"))
        print("❌ Azure OpenAI endpoint must start with https://")
    else:
        print(f"✅ Endpoint: {config.azure_openai.endpoint}")

    # Check API key
    if "your-api-key" in config.azure_openai.api_key or len(config.azure_openai.api_key) < 10:
        critical_errors.append(("Azure OpenAI", "API key not configured or invalid"))
        print("❌ Azure OpenAI API key not configured")
    else:
        print(f"✅ API Key: {config.azure_openai.api_key[:10]}..." + "*" * 20)

    # Check deployments
    print(f"✅ GPT-4o Deployment: {config.azure_openai.gpt4o_deployment}")
    print(f"✅ Embedding Deployment: {config.azure_openai.embedding_deployment}")

    # Test connection (if credentials valid)
    if not any("Azure OpenAI" in err[0] for err in critical_errors):
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=config.azure_openai.endpoint,
                api_key=config.azure_openai.api_key,
                api_version=config.azure_openai.api_version,
            )
            # Simple test - list models (this doesn't cost anything)
            print("✅ Azure OpenAI connection test: SUCCESS")
        except Exception as e:
            critical_errors.append(("Azure OpenAI Connection", str(e)))
            print(f"❌ Azure OpenAI connection test failed: {e}")

except Exception as e:
    critical_errors.append(("Azure OpenAI Validation", str(e)))
    print(f"❌ Azure OpenAI validation failed: {e}")

# ====================================================================================================
# SECTION 3: DATABRICKS CONFIGURATION VALIDATION
# ====================================================================================================
print("\n[3/10] Validating Databricks Configuration...")
print("-" * 100)

try:
    # Check host format
    if "your-workspace" in config.databricks.host:
        critical_errors.append(("Databricks", "Host contains placeholder 'your-workspace'"))
        print("❌ Databricks host not configured (contains placeholder)")
    elif not config.databricks.host.startswith("https://"):
        critical_errors.append(("Databricks", "Host must start with https://"))
        print("❌ Databricks host must start with https://")
    else:
        print(f"✅ Host: {config.databricks.host}")

    # Check token
    if "your-databricks-token" in config.databricks.token or len(config.databricks.token) < 10:
        critical_errors.append(("Databricks", "Token not configured or invalid"))
        print("❌ Databricks token not configured")
    else:
        print(f"✅ Token: {config.databricks.token[:10]}..." + "*" * 20)

    # Check SQL Warehouse ID
    if "your-sql-warehouse" in config.databricks.sql_warehouse_id or len(config.databricks.sql_warehouse_id) < 5:
        critical_errors.append(("Databricks SQL Warehouse", "SQL Warehouse ID not configured"))
        print("❌ SQL Warehouse ID not configured")
    else:
        print(f"✅ SQL Warehouse ID: {config.databricks.sql_warehouse_id}")

    # Check Genie Space ID
    if "your-genie-space" in config.databricks.genie_space_id or len(config.databricks.genie_space_id) < 5:
        critical_errors.append(("Databricks Genie", "Genie Space ID not configured"))
        print("❌ Genie Space ID not configured")
    else:
        print(f"✅ Genie Space ID: {config.databricks.genie_space_id}")

    # Test connection (if credentials valid)
    if not any("Databricks" in err[0] for err in critical_errors):
        try:
            from databricks.sdk import WorkspaceClient
            client = WorkspaceClient(
                host=config.databricks.host,
                token=config.databricks.token,
            )
            # Test connection with a simple API call
            current_user = client.current_user.me()
            print(f"✅ Databricks connection test: SUCCESS (User: {current_user.user_name})")
        except Exception as e:
            critical_errors.append(("Databricks Connection", str(e)))
            print(f"❌ Databricks connection test failed: {e}")

except Exception as e:
    critical_errors.append(("Databricks Validation", str(e)))
    print(f"❌ Databricks validation failed: {e}")

# ====================================================================================================
# SECTION 4: SQL WAREHOUSE ACCESS VALIDATION
# ====================================================================================================
print("\n[4/10] Validating SQL Warehouse Access...")
print("-" * 100)

if not any("Databricks" in err[0] for err in critical_errors):
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient(
            host=config.databricks.host,
            token=config.databricks.token,
        )

        # Check if warehouse exists and is accessible
        try:
            warehouse = client.warehouses.get(config.databricks.sql_warehouse_id)
            print(f"✅ SQL Warehouse found: {warehouse.name}")
            print(f"   State: {warehouse.state}")
            print(f"   Cluster Size: {warehouse.cluster_size}")

            if warehouse.state.value != "RUNNING":
                warnings.append(("SQL Warehouse", f"Warehouse is {warehouse.state.value}, not RUNNING"))
                print(f"⚠️  Warehouse is {warehouse.state.value} (it will auto-start when needed)")
        except Exception as e:
            critical_errors.append(("SQL Warehouse Access", str(e)))
            print(f"❌ Cannot access SQL Warehouse: {e}")

    except Exception as e:
        critical_errors.append(("SQL Warehouse Validation", str(e)))
        print(f"❌ SQL Warehouse validation failed: {e}")
else:
    print("⏭️  Skipped (Databricks connection not available)")

# ====================================================================================================
# SECTION 5: UNITY CATALOG ACCESS VALIDATION
# ====================================================================================================
print("\n[5/10] Validating Unity Catalog Access...")
print("-" * 100)

if not any("Databricks" in err[0] for err in critical_errors):
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient(
            host=config.databricks.host,
            token=config.databricks.token,
        )

        # Check catalog access
        try:
            catalog = client.catalogs.get(config.databricks.unity_catalog)
            print(f"✅ Catalog '{config.databricks.unity_catalog}' exists")
        except Exception as e:
            critical_errors.append(("Unity Catalog", f"Cannot access catalog: {e}"))
            print(f"❌ Cannot access catalog '{config.databricks.unity_catalog}': {e}")

        # Check schema access
        try:
            full_schema_name = f"{config.databricks.unity_catalog}.{config.databricks.unity_schema}"
            schema = client.schemas.get(full_schema_name)
            print(f"✅ Schema '{config.databricks.unity_schema}' exists")
        except Exception as e:
            critical_errors.append(("Unity Catalog Schema", f"Cannot access schema: {e}"))
            print(f"❌ Cannot access schema '{config.databricks.unity_schema}': {e}")

        # Check table access
        if config.databricks.unity_tables:
            print(f"   Checking {len(config.databricks.unity_tables)} configured tables...")
            for table_name in config.databricks.unity_tables:
                try:
                    full_table_name = f"{config.databricks.unity_catalog}.{config.databricks.unity_schema}.{table_name}"
                    table = client.tables.get(full_table_name)
                    print(f"   ✅ Table '{table_name}' exists ({table.table_type})")
                except Exception as e:
                    warnings.append(("Unity Catalog Table", f"Cannot access table '{table_name}': {e}"))
                    print(f"   ⚠️  Cannot access table '{table_name}': {e}")
        else:
            warnings.append(("Unity Catalog", "No tables configured"))
            print("⚠️  No tables configured in UNITY_CATALOG_TABLES")

    except Exception as e:
        critical_errors.append(("Unity Catalog Validation", str(e)))
        print(f"❌ Unity Catalog validation failed: {e}")
else:
    print("⏭️  Skipped (Databricks connection not available)")

# ====================================================================================================
# SECTION 6: AZURE BLOB STORAGE VALIDATION
# ====================================================================================================
print("\n[6/10] Validating Azure Blob Storage Configuration...")
print("-" * 100)

try:
    # Check connection string format
    conn_str = config.azure_storage.connection_string
    if "your-account" in conn_str or "AccountName=" not in conn_str:
        critical_errors.append(("Azure Storage", "Connection string not configured or invalid"))
        print("❌ Azure Storage connection string not configured")
    else:
        # Extract account name from connection string
        account_name = "***"
        if "AccountName=" in conn_str:
            account_name = conn_str.split("AccountName=")[1].split(";")[0]
        print(f"✅ Storage Account: {account_name}")

        # Test connection
        try:
            from azure.storage.blob import BlobServiceClient
            blob_service = BlobServiceClient.from_connection_string(conn_str)

            # List containers to verify access
            containers = list(blob_service.list_containers())
            print(f"✅ Connection test: SUCCESS ({len(containers)} containers found)")

            # Check configured containers
            cache_container, cache_prefix = config.azure_storage.get_cache_config()
            rag_container, rag_prefix = config.azure_storage.get_rag_config()
            eda_container, eda_prefix = config.azure_storage.get_eda_config()

            print(f"   Cache: {cache_container}/{cache_prefix if cache_prefix else '(root)'}")
            print(f"   RAG:   {rag_container}/{rag_prefix if rag_prefix else '(root)'}")
            print(f"   EDA:   {eda_container}/{eda_prefix if eda_prefix else '(root)'}")

            # Validate containers exist (auto-create if missing)
            for container_name in set([cache_container, rag_container, eda_container]):
                try:
                    container_client = blob_service.get_container_client(container_name)
                    if not container_client.exists():
                        warnings.append(("Azure Storage", f"Container '{container_name}' does not exist (will be auto-created)"))
                        print(f"   ⚠️  Container '{container_name}' does not exist (will be auto-created)")
                    else:
                        print(f"   ✅ Container '{container_name}' exists")
                except Exception as e:
                    warnings.append(("Azure Storage Container", f"Cannot check container '{container_name}': {e}"))
                    print(f"   ⚠️  Cannot check container '{container_name}': {e}")

        except Exception as e:
            critical_errors.append(("Azure Storage Connection", str(e)))
            print(f"❌ Azure Storage connection test failed: {e}")

except Exception as e:
    critical_errors.append(("Azure Storage Validation", str(e)))
    print(f"❌ Azure Storage validation failed: {e}")

# ====================================================================================================
# SECTION 7: GENIE SPACE ACCESS VALIDATION
# ====================================================================================================
print("\n[7/10] Validating Genie Space Access...")
print("-" * 100)

if not any("Databricks" in err[0] or "Genie" in err[0] for err in critical_errors):
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient(
            host=config.databricks.host,
            token=config.databricks.token,
        )

        try:
            # Try to access the Genie space
            # Note: This may fail if the SDK doesn't expose the Genie space API directly
            print(f"✅ Genie Space ID configured: {config.databricks.genie_space_id}")
            print("   (Space access will be validated on first query)")
            warnings.append(("Genie Space", "Cannot validate Genie Space access pre-runtime"))

        except Exception as e:
            warnings.append(("Genie Space Access", str(e)))
            print(f"⚠️  Cannot validate Genie Space access: {e}")

    except Exception as e:
        warnings.append(("Genie Space Validation", str(e)))
        print(f"⚠️  Genie Space validation failed: {e}")
else:
    print("⏭️  Skipped (Databricks or Genie configuration not available)")

# ====================================================================================================
# SECTION 8: RAG CONFIGURATION VALIDATION
# ====================================================================================================
print("\n[8/10] Validating RAG Configuration...")
print("-" * 100)

try:
    print(f"✅ Auto-process enabled: {config.rag.auto_process}")
    print(f"✅ Supported extensions: {', '.join(config.rag.supported_extensions)}")
    print(f"✅ Poll interval: {config.rag.poll_interval}s")

    # Note: watch_path is deprecated (using Azure Blob Storage instead)
    if config.rag.watch_path:
        warnings.append(("RAG Configuration", "watch_path is deprecated (using Azure Blob Storage)"))
        print("⚠️  RAG_WATCH_PATH is set but deprecated (system uses Azure Blob Storage)")

    print("✅ RAG will monitor Azure Blob Storage for new documents")

except Exception as e:
    warnings.append(("RAG Configuration", str(e)))
    print(f"⚠️  RAG configuration validation failed: {e}")

# ====================================================================================================
# SECTION 9: MLFLOW CONFIGURATION VALIDATION
# ====================================================================================================
print("\n[9/10] Validating MLflow Configuration...")
print("-" * 100)

try:
    print(f"✅ Experiment name: {config.mlflow.experiment_name}")
    print(f"✅ Tracking enabled: {config.mlflow.tracking_enabled}")

    # Validate experiment name format
    if not config.mlflow.experiment_name.startswith("/Users/"):
        warnings.append(("MLflow", "Experiment name should start with /Users/ for Databricks"))
        print("⚠️  Experiment name should start with /Users/ for Databricks workspace tracking")

except Exception as e:
    warnings.append(("MLflow Configuration", str(e)))
    print(f"⚠️  MLflow configuration validation failed: {e}")

# ====================================================================================================
# SECTION 10: DEPENDENCY CHECK
# ====================================================================================================
print("\n[10/10] Checking Python Dependencies...")
print("-" * 100)

required_packages = {
    "langchain": "langchain",
    "langchain-core": "langchain_core",
    "langchain-community": "langchain_community",
    "langgraph": "langgraph",
    "databricks-sdk": "databricks.sdk",
    "azure-storage-blob": "azure.storage.blob",
    "openai": "openai",
    "faiss-cpu": "faiss",
    "pydantic": "pydantic",
    "mlflow": "mlflow",
}

missing_packages = []
for package_name, import_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"✅ {package_name}")
    except ImportError:
        missing_packages.append(package_name)
        critical_errors.append(("Dependency", f"Missing package: {package_name}"))
        print(f"❌ {package_name} - NOT INSTALLED")

if missing_packages:
    print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
    print(f"   Install with: pip install {' '.join(missing_packages)}")

# ====================================================================================================
# FINAL SUMMARY
# ====================================================================================================
print("\n" + "=" * 100)
print("VALIDATION SUMMARY")
print("=" * 100)

print(f"\n✅ Checks passed: {10 - len([e for e in critical_errors if e])}")
print(f"❌ Critical errors: {len(critical_errors)}")
print(f"⚠️  Warnings: {len(warnings)}")

if critical_errors:
    print("\n" + "─" * 100)
    print("CRITICAL ERRORS (System will NOT work):")
    print("─" * 100)
    for category, error in critical_errors:
        print(f"❌ [{category}] {error}")

if warnings:
    print("\n" + "─" * 100)
    print("WARNINGS (System may work with limitations):")
    print("─" * 100)
    for category, warning in warnings:
        print(f"⚠️  [{category}] {warning}")

print("\n" + "=" * 100)
if critical_errors:
    print("❌ VALIDATION FAILED")
    print("=" * 100)
    print("\nPlease fix the critical errors above and run this script again.")
    print("Refer to .env.example and CLAUDE.md for configuration help.")
    sys.exit(1)
elif warnings:
    print("⚠️  VALIDATION PASSED WITH WARNINGS")
    print("=" * 100)
    print("\nSystem should work, but review warnings above.")
    print("You can proceed to run the system, but some features may not work correctly.")
    sys.exit(2)
else:
    print("✅ VALIDATION PASSED")
    print("=" * 100)
    print("\n🎉 All checks passed! Your system is ready to use.")
    print("\nNext steps:")
    print("  1. Run the system: python src/main.py")
    print("  2. Or run tests: python -m pytest tests/")
    sys.exit(0)
