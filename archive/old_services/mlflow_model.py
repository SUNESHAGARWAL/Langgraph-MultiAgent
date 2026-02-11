"""
MLflow PyFunc Model Wrapper for Multi-Agent Orchestrator

This module provides an MLflow PyFunc wrapper that enables:
- Deployment to Databricks Model Serving
- Batch prediction support
- Automatic experiment tracking
- Standard DataFrame input/output interface

Usage:
    # Register model
    python deploy_model.py --register-model

    # Serve model
    mlflow models serve -m "models:/MultiAgentOrchestrator/production" -p 5000

    # Query model
    import pandas as pd
    import requests

    df = pd.DataFrame({
        "question": ["What were sales last quarter?"],
        "thread_id": ["user-123"]
    })

    response = requests.post(
        "http://localhost:5000/invocations",
        json={"dataframe_split": df.to_dict(orient="split")}
    )
"""

import mlflow
import mlflow.pyfunc
import pandas as pd
import uuid
from typing import Dict, Any, List
import logging

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class MultiAgentModel(mlflow.pyfunc.PythonModel):
    """
    MLflow PyFunc wrapper for Multi-Agent Orchestrator.

    This model provides a standard interface for:
    - Single and batch predictions
    - Conversation memory management
    - Metrics tracking and logging
    - Databricks Model Serving compatibility
    """

    def load_context(self, context):
        """
        Load model and dependencies when model is loaded.

        Args:
            context: MLflow context with artifacts and metadata
        """
        logger.info("Loading Multi-Agent Orchestrator model...")

        try:
            # Import here to avoid loading during model logging
            from src.agent_enhanced import get_agent
            from src.utils.metrics import get_metrics_tracker

            # Initialize agent
            self.agent = get_agent()
            self.metrics = get_metrics_tracker()

            logger.info("✓ Multi-Agent Orchestrator loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def predict(self, context, model_input):
        """
        Run predictions on input data.

        Args:
            context: MLflow context
            model_input: pandas DataFrame with columns:
                - question: str - User question
                - thread_id: str (optional) - Conversation thread ID

        Returns:
            pandas DataFrame with columns:
                - answer: str - Final answer
                - query_id: str - Unique query identifier
                - thread_id: str - Conversation thread
                - iterations: int - Number of iterations
                - duration: float - Query duration in seconds
                - cost: float - Estimated cost in USD
                - cache_hit: bool - Whether result was cached
                - success: bool - Whether query succeeded
                - error: str (optional) - Error message if failed
        """
        logger.info(f"Processing {len(model_input)} queries...")

        results = []

        for idx, row in model_input.iterrows():
            question = row.get("question", "")
            thread_id = row.get("thread_id", str(uuid.uuid4()))

            if not question:
                logger.warning(f"Empty question at row {idx}")
                results.append({
                    "answer": "Error: Empty question",
                    "query_id": str(uuid.uuid4()),
                    "thread_id": thread_id,
                    "iterations": 0,
                    "duration": 0.0,
                    "cost": 0.0,
                    "cache_hit": False,
                    "success": False,
                    "error": "Empty question provided"
                })
                continue

            # Process single query
            result = self._process_single_query(question, thread_id)
            results.append(result)

        # Convert to DataFrame
        output_df = pd.DataFrame(results)

        logger.info(f"✓ Processed {len(results)} queries successfully")

        return output_df

    def _process_single_query(self, question: str, thread_id: str) -> Dict[str, Any]:
        """
        Process a single query.

        Args:
            question: User question
            thread_id: Conversation thread ID

        Returns:
            Dictionary with query results
        """
        query_id = str(uuid.uuid4())

        logger.info(f"Query {query_id}: {question[:100]}...")

        # Start metrics tracking
        metrics = self.metrics.start_query(query_id, question, thread_id)

        try:
            # Prepare initial state
            initial_state = {
                "messages": [HumanMessage(content=question)],
                "next_agent": "",
                "iterations": 0,
                "final_answer": "",
                "query_id": query_id,
                "parallel_agents": None,
                "validation_result": None,
                "validation_feedback": None,
            }

            # Invoke agent with conversation memory
            result = self.agent.invoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "query_id": query_id
                    }
                }
            )

            # Extract results
            final_answer = result.get("final_answer", "")
            iterations = result.get("iterations", 0)

            # End metrics tracking
            self.metrics.end_query(
                query_id,
                success=True,
                iterations=iterations,
                final_answer=final_answer
            )

            # Get metrics
            query_metrics = self.metrics.get_query_metrics(query_id)

            # Build result
            return {
                "answer": final_answer,
                "query_id": query_id,
                "thread_id": thread_id,
                "iterations": iterations,
                "duration": query_metrics.duration() if query_metrics else 0.0,
                "cost": query_metrics.estimated_cost() if query_metrics else 0.0,
                "cache_hit": query_metrics.cache_hits > 0 if query_metrics else False,
                "success": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"Query {query_id} failed: {e}")

            # End metrics tracking with error
            self.metrics.end_query(
                query_id,
                success=False,
                iterations=0,
                error=str(e)
            )

            return {
                "answer": f"Error: {str(e)}",
                "query_id": query_id,
                "thread_id": thread_id,
                "iterations": 0,
                "duration": 0.0,
                "cost": 0.0,
                "cache_hit": False,
                "success": False,
                "error": str(e)
            }


def get_model_signature():
    """
    Get MLflow model signature for registration.

    Returns:
        mlflow.models.signature.ModelSignature
    """
    from mlflow.models.signature import ModelSignature
    from mlflow.types.schema import Schema, ColSpec

    input_schema = Schema([
        ColSpec("string", "question"),
        ColSpec("string", "thread_id", optional=True),
    ])

    output_schema = Schema([
        ColSpec("string", "answer"),
        ColSpec("string", "query_id"),
        ColSpec("string", "thread_id"),
        ColSpec("long", "iterations"),
        ColSpec("double", "duration"),
        ColSpec("double", "cost"),
        ColSpec("boolean", "cache_hit"),
        ColSpec("boolean", "success"),
        ColSpec("string", "error", optional=True),
    ])

    return ModelSignature(inputs=input_schema, outputs=output_schema)


def get_conda_env():
    """
    Get conda environment for model deployment.

    Returns:
        Dictionary with conda environment specification
    """
    import sys

    return {
        "name": "multi_agent_env",
        "channels": ["conda-forge"],
        "dependencies": [
            f"python={sys.version_info.major}.{sys.version_info.minor}",
            "pip",
            {
                "pip": [
                    "mlflow>=2.19.0",
                    "langgraph>=1.0.7",
                    "langchain>=0.3.0",
                    "langchain-core>=0.3.0",
                    "langchain-community>=0.3.0",
                    "langchain-openai>=0.2.0",
                    "databricks-sdk>=0.35.0",
                    "databricks-langchain>=0.14.0",
                    "faiss-cpu>=1.8.0",
                    "pypdf>=5.0.0",
                    "python-docx>=1.1.0",
                    "pandas>=2.2.0",
                    "openpyxl>=3.1.0",
                    "python-pptx>=1.0.0",
                    "python-dotenv>=1.0.0",
                    "pydantic>=2.9.0",
                    "pydantic-settings>=2.6.0",
                    "psycopg2-binary>=2.9.9",
                    "langgraph-checkpoint-postgres>=1.0.0",
                ]
            }
        ]
    }


def get_example_input():
    """
    Get example input for model signature.

    Returns:
        pandas DataFrame with example input
    """
    return pd.DataFrame({
        "question": [
            "What were our top 5 products by revenue last quarter?",
            "What is our refund policy?"
        ],
        "thread_id": ["user-123", "user-456"]
    })


def log_model(
    model_name: str = "MultiAgentOrchestrator",
    experiment_name: str = "/Users/default/multi-agent",
    registered_model_name: str = None
):
    """
    Log model to MLflow with all artifacts and metadata.

    Args:
        model_name: Artifact path for model
        experiment_name: MLflow experiment name
        registered_model_name: Name for model registry (if registering)

    Returns:
        mlflow.entities.Run - The logged run
    """
    import mlflow

    # Set experiment
    mlflow.set_experiment(experiment_name)

    # Start run
    with mlflow.start_run(run_name="multi_agent_model_v3.0.0") as run:
        logger.info(f"Logging model to experiment: {experiment_name}")

        # Log parameters
        mlflow.log_param("model_version", "3.0.0")
        mlflow.log_param("agent_type", "multi_agent_supervisor")
        mlflow.log_param("features", "caching,validation,parallel,metrics")

        # Create model instance
        model = MultiAgentModel()

        # Get signature and conda env
        signature = get_model_signature()
        conda_env = get_conda_env()
        example_input = get_example_input()

        # Log model
        mlflow.pyfunc.log_model(
            artifact_path=model_name,
            python_model=model,
            conda_env=conda_env,
            signature=signature,
            input_example=example_input,
            registered_model_name=registered_model_name,
        )

        logger.info(f"✓ Model logged successfully")
        logger.info(f"  Run ID: {run.info.run_id}")
        logger.info(f"  Artifact URI: {run.info.artifact_uri}")

        if registered_model_name:
            logger.info(f"  Registered Model: {registered_model_name}")

        return run
