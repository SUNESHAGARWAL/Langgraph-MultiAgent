"""
Multi-Agent Orchestrator System for Databricks Genie Integration.
"""

__version__ = "1.0.0"
__author__ = "Claude AI"

# Lazy imports to avoid loading heavy dependencies during validation
def _lazy_import_orchestrator():
    from src.main import MultiAgentOrchestrator
    return MultiAgentOrchestrator

# Only import if explicitly requested
__all__ = ["__version__", "__author__"]

# Make MultiAgentOrchestrator available via getattr for backward compatibility
def __getattr__(name):
    if name == "MultiAgentOrchestrator":
        return _lazy_import_orchestrator()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
