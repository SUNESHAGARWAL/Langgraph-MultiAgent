"""
Comprehensive Test Suite for Multi-Agent Orchestrator

Run with: pytest tests/test_system_comprehensive.py -v --cov=src
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# 1. CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Test configuration loading and validation."""

    def test_config_singleton(self):
        """Test that config is a singleton."""
        from src.core.config import Config

        config1 = Config.get_instance()
        config2 = Config.get_instance()

        assert config1 is config2, "Config should be singleton"

    def test_database_config_exists(self):
        """Test that database config was added."""
        from src.core.config import config

        assert hasattr(config, 'database'), "Config should have database"
        assert hasattr(config.database, 'postgres_url'), "Database config should have postgres_url"
        assert hasattr(config.database, 'use_persistent_memory'), "Database config should have use_persistent_memory"

    def test_cache_config_exists(self):
        """Test that cache config has new fields."""
        from src.core.config import config

        assert hasattr(config.cache, 'similarity_threshold'), "Cache should have similarity_threshold"
        assert hasattr(config.cache, 'ttl_hours'), "Cache should have ttl_hours"
        assert hasattr(config.cache, 'cache_dir'), "Cache should have cache_dir"


# ============================================================================
# 2. METRICS TRACKER TESTS
# ============================================================================

class TestMetricsTracker:
    """Test metrics tracking functionality."""

    def test_singleton_tracker(self):
        """Test that metrics tracker is singleton."""
        from src.utils.metrics import get_metrics_tracker

        tracker1 = get_metrics_tracker()
        tracker2 = get_metrics_tracker()

        assert tracker1 is tracker2, "Metrics tracker should be singleton"

    def test_start_query(self):
        """Test starting a query."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()  # Clear previous metrics

        metrics = tracker.start_query("test-001", "test question", "thread-001")

        assert metrics.query_id == "test-001"
        assert metrics.question == "test question"
        assert metrics.thread_id == "thread-001"
        assert metrics.iterations == 0

    def test_track_agent_call(self):
        """Test tracking agent calls."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        tracker.start_query("test-002", "test", "thread-001")
        tracker.track_agent_call("test-002", "supervisor")
        tracker.track_agent_call("test-002", "SQL_Specialist")

        metrics = tracker.get_query_metrics("test-002")

        assert metrics.supervisor_calls == 1
        assert metrics.genie_calls == 1

    def test_cache_tracking(self):
        """Test cache hit/miss tracking."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        tracker.start_query("test-003", "test", "thread-001")
        tracker.track_cache_hit("test-003")
        tracker.track_cache_miss("test-003")

        metrics = tracker.get_query_metrics("test-003")

        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 1
        assert metrics.cache_hit_rate() == 0.5

    def test_validation_tracking(self):
        """Test validation result tracking."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        tracker.start_query("test-004", "test", "thread-001")
        tracker.track_validation("test-004", "RELEVANT")
        tracker.track_validation("test-004", "PARTIAL")
        tracker.track_validation("test-004", "NOT_RELEVANT")

        metrics = tracker.get_query_metrics("test-004")

        assert metrics.validation_passed == 1
        assert metrics.validation_partial == 1
        assert metrics.validation_failed == 1

    def test_end_query(self):
        """Test ending a query."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        tracker.start_query("test-005", "test", "thread-001")
        result = tracker.end_query("test-005", True, 2, "final answer")

        assert result.success == True
        assert result.iterations == 2
        assert result.final_answer == "final answer"
        assert result.end_time is not None

    def test_aggregate_stats(self):
        """Test aggregate statistics."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        # Add a few queries
        for i in range(3):
            query_id = f"test-{i}"
            tracker.start_query(query_id, "test", "thread-001")
            tracker.end_query(query_id, i < 2, 1, "answer")  # 2 successes, 1 failure

        stats = tracker.get_aggregate_stats()

        assert stats['total_queries'] == 3
        assert stats['successful'] == 2
        assert stats['failed'] == 1
        assert stats['success_rate'] == pytest.approx(2/3, 0.01)


# ============================================================================
# 3. MLFLOW MODEL TESTS
# ============================================================================

class TestMLflowModel:
    """Test MLflow model wrapper."""

    def test_model_signature(self):
        """Test model signature generation."""
        from src.mlflow_model import get_model_signature

        signature = get_model_signature()

        # Check input schema
        input_cols = [spec.name for spec in signature.inputs.inputs]
        assert 'question' in input_cols
        assert 'thread_id' in input_cols

        # Check output schema
        output_cols = [spec.name for spec in signature.outputs.inputs]
        assert 'answer' in output_cols
        assert 'query_id' in output_cols
        assert 'duration' in output_cols
        assert 'cost' in output_cols
        assert 'cache_hit' in output_cols
        assert 'success' in output_cols

    def test_conda_env(self):
        """Test conda environment generation."""
        from src.mlflow_model import get_conda_env

        conda_env = get_conda_env()

        assert 'name' in conda_env
        assert 'dependencies' in conda_env
        assert isinstance(conda_env['dependencies'], list)

        # Check pip dependencies
        pip_deps = [d for d in conda_env['dependencies'] if isinstance(d, dict) and 'pip' in d]
        assert len(pip_deps) > 0

        # Check for key packages
        pip_packages = pip_deps[0]['pip']
        assert any('langgraph' in pkg for pkg in pip_packages)
        assert any('databricks-langchain' in pkg for pkg in pip_packages)
        assert any('mlflow' in pkg for pkg in pip_packages)

    def test_example_input(self):
        """Test example input generation."""
        from src.mlflow_model import get_example_input

        example = get_example_input()

        assert isinstance(example, pd.DataFrame)
        assert 'question' in example.columns
        assert 'thread_id' in example.columns
        assert len(example) > 0


# ============================================================================
# 4. FASTAPI TESTS
# ============================================================================

class TestFastAPI:
    """Test FastAPI server."""

    def test_app_creation(self):
        """Test that app is created properly."""
        from src.api import app

        assert app.title == "Multi-Agent Orchestrator API"
        assert app.version == "3.0.0"

    def test_query_request_model(self):
        """Test QueryRequest validation."""
        from src.api import QueryRequest

        # Valid request
        req = QueryRequest(question="test question", thread_id="test-123")
        assert req.question == "test question"
        assert req.thread_id == "test-123"

        # Test with optional thread_id
        req2 = QueryRequest(question="test question")
        assert req2.question == "test question"
        assert req2.thread_id is None

    def test_query_request_validation(self):
        """Test that empty question is rejected."""
        from src.api import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryRequest(question="")  # Empty question should fail

    def test_query_response_model(self):
        """Test QueryResponse model."""
        from src.api import QueryResponse

        resp = QueryResponse(
            query_id="test-001",
            answer="test answer",
            thread_id="thread-001",
            iterations=2,
            duration=5.0,
            cost=0.01,
            cache_hit=False,
            success=True
        )

        assert resp.query_id == "test-001"
        assert resp.answer == "test answer"
        assert resp.iterations == 2
        assert resp.success == True


# ============================================================================
# 5. DEPLOYMENT SCRIPT TESTS
# ============================================================================

class TestDeployment:
    """Test deployment script functions."""

    def test_deployment_imports(self):
        """Test that deployment script imports correctly."""
        import deploy_model

        assert hasattr(deploy_model, 'validate_environment')
        assert hasattr(deploy_model, 'log_model_to_mlflow')
        assert hasattr(deploy_model, 'promote_model_stage')
        assert hasattr(deploy_model, 'generate_deployment_readme')
        assert hasattr(deploy_model, 'main')


# ============================================================================
# 6. INTEGRATION TESTS (Without Dependencies)
# ============================================================================

class TestIntegration:
    """Integration tests that don't require external dependencies."""

    def test_metrics_workflow(self):
        """Test complete metrics workflow."""
        from src.utils.metrics import get_metrics_tracker

        tracker = get_metrics_tracker()
        tracker.clear()

        # Simulate a complete query workflow
        query_id = "integration-001"

        # 1. Start query
        metrics = tracker.start_query(query_id, "test question", "thread-001")

        # 2. Track supervisor call
        tracker.track_agent_call(query_id, "supervisor")

        # 3. Track SQL call (cache miss)
        tracker.track_cache_miss(query_id)
        tracker.track_agent_call(query_id, "SQL_Specialist")

        # 4. Track validation
        tracker.track_validation(query_id, "RELEVANT")

        # 5. Track synthesis
        tracker.track_agent_call(query_id, "synthesis")

        # 6. End query
        result = tracker.end_query(query_id, True, 2, "final answer")

        # Verify complete workflow
        assert result.supervisor_calls == 1
        assert result.genie_calls == 1
        assert result.synthesis_calls == 1
        assert result.cache_misses == 1
        assert result.validation_passed == 1
        assert result.success == True
        assert result.iterations == 2


# ============================================================================
# 7. FILE STRUCTURE TESTS
# ============================================================================

class TestFileStructure:
    """Test that all required files exist."""

    def test_required_files_exist(self):
        """Test that all required files exist."""
        required_files = [
            'src/utils/cache.py',
            'src/utils/metrics.py',
            'src/agent_enhanced.py',
            'src/mlflow_model.py',
            'src/api.py',
            'deploy_model.py',
            'requirements.txt',
            'CLAUDE.md',
            'REFERENCE.md',
            'SKILLS.md',
        ]

        for filepath in required_files:
            assert Path(filepath).exists(), f"{filepath} should exist"

    def test_src_structure(self):
        """Test src directory structure."""
        assert Path('src').is_dir()
        assert Path('src/utils').is_dir()
        assert Path('src/core').is_dir()
        assert Path('src/__init__.py').exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
