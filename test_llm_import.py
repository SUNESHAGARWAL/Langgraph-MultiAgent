"""
Quick test to verify LLM utility imports correctly.
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing LLM utility import...")
print("-" * 40)

try:
    from src.core.config import config
    print("✓ Config imported")

    from src.utils.llm import get_llm, get_mini_llm
    print("✓ LLM utilities imported")

    # Check config structure
    print("\n📋 Config structure:")
    print(f"  azure_openai.endpoint: {config.azure_openai.endpoint[:30]}...")
    print(f"  azure_openai.gpt4o_deployment: {config.azure_openai.gpt4o_deployment}")
    print(f"  azure_openai.temperature: {config.azure_openai.temperature}")
    print(f"  azure_openai.max_tokens: {config.azure_openai.max_tokens}")

    # Try to create LLM instance
    print("\n🤖 Creating LLM instance...")
    llm = get_llm()
    print(f"✓ LLM created: {type(llm).__name__}")

    print("\n✅ All tests passed!")
    print("LLM utility is working correctly.")

except AttributeError as e:
    print(f"❌ AttributeError: {e}")
    print("\nConfig attributes:")
    print(dir(config))

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
