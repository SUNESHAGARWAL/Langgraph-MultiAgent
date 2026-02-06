"""
Diagnostic script to check Databricks SDK structure
"""
import sys

print("=== Databricks SDK Diagnostic ===\n")

try:
    from databricks import sdk
    print(f"✅ databricks-sdk installed: {sdk.__version__}")
except Exception as e:
    print(f"❌ databricks-sdk not installed: {e}")
    sys.exit(1)

print("\n--- Checking workspace module ---")
try:
    from databricks.sdk.service import workspace
    print(f"✅ workspace module exists")

    # List all classes in workspace
    print("\nAvailable classes in workspace module:")
    for name in dir(workspace):
        if not name.startswith('_'):
            print(f"  - {name}")

except Exception as e:
    print(f"❌ Error: {e}")

print("\n--- Checking for Genie-related classes ---")
try:
    from databricks.sdk import service

    # Check if there's a genie module
    if hasattr(service, 'genie'):
        print("✅ Found genie module in service")
        genie_module = service.genie
        print("\nAvailable in genie module:")
        for name in dir(genie_module):
            if not name.startswith('_') and 'Genie' in name:
                print(f"  - {name}")
    else:
        print("⚠️ No genie module found")

    # Check workspace for Genie classes
    print("\nGenie-related in workspace:")
    for name in dir(workspace):
        if 'Genie' in name or 'genie' in name:
            print(f"  - {name}")

except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== End Diagnostic ===")
