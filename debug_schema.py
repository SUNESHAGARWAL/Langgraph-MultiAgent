"""
Debug script to check Unity Catalog schema reading
"""

from databricks.sdk import WorkspaceClient
from src.core.config import config

# Initialize client
client = WorkspaceClient(
    host=config.databricks.host,
    token=config.databricks.token,
)

# Test reading one table
test_table = "westeurope_extollo_it_eu_fact_finder_prod_adbv.mbindia.pc_sales"

print(f"Testing Unity Catalog read for: {test_table}")
print("=" * 80)

try:
    # Try to get table info
    table_info = client.tables.get(test_table)

    print(f"✅ Table found: {table_info.name}")
    print(f"   Table type: {table_info.table_type}")
    print(f"   Comment: {table_info.comment or 'No comment'}")
    print(f"   Columns: {len(table_info.columns) if table_info.columns else 0}")
    print()

    if table_info.columns:
        print("Columns loaded:")
        for col in table_info.columns[:10]:  # Show first 10
            print(f"  - {col.name} ({col.type_name.value if col.type_name else 'UNKNOWN'}): {col.comment or 'No comment'}")
    else:
        print("❌ NO COLUMNS LOADED!")
        print("This is why the system can't answer questions.")

except Exception as e:
    print(f"❌ Error reading table: {e}")
    print()
    print("Possible issues:")
    print("1. Table name format incorrect")
    print("2. Insufficient permissions")
    print("3. Table doesn't exist")

print()
print("=" * 80)
print("Configured tables:")
for table in config.databricks.unity_tables:
    print(f"  - {table}")
