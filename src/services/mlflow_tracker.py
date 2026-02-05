"""
MLflow tracking service for experiment management and logging.
"""

import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from functools import wraps

import mlflow
from mlflow.entities import RunStatus

from src.core.config import config
from src.utils.logging import get_logger, get_session_id, trace_function

logger = get_logger(__name__)


class MLflowTracker:
    """
    MLflow tracking service for managing experiments and runs.
    """

    def __init__(self):
        self._setup_mlflow()
        self.active_run_id: Optional[str] = None

    def _setup_mlflow(self):
        """Setup MLflow tracking"""
        try:
            # Set tracking URI (databricks or custom)
            mlflow.set_tracking_uri(config.mlflow.tracking_uri)

            # Set or create experiment
            try:
                experiment = mlflow.get_experiment_by_name(config.mlflow.experiment_name)
                if experiment is None:
                    experiment_id = mlflow.create_experiment(config.mlflow.experiment_name)
                    logger.info(f"Created MLflow experiment: {config.mlflow.experiment_name}")
                else:
                    experiment_id = experiment.experiment_id
                    logger.info(f"Using existing MLflow experiment: {config.mlflow.experiment_name}")

                mlflow.set_experiment(experiment_id=experiment_id)

            except Exception as e:
                logger.warning(f"Could not set experiment, using default: {e}")
                mlflow.set_experiment(config.mlflow.experiment_name)

            # Enable system metrics if configured
            if config.mlflow.enable_system_metrics:
                mlflow.enable_system_metrics_logging()

            logger.info("MLflow tracking initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize MLflow: {e}")
            raise

    @contextmanager
    @trace_function("mlflow_run")
    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        nested: bool = False,
    ):
        """
        Context manager for MLflow run.

        Args:
            run_name: Optional run name
            tags: Optional tags dict
            nested: Whether this is a nested run

        Usage:
            with tracker.start_run(run_name="my_run"):
                mlflow.log_param("param", value)
                mlflow.log_metric("metric", value)
        """
        # Add default tags
        default_tags = {
            "app_name": config.app.name,
            "app_version": config.app.version,
            "environment": config.app.environment,
        }

        # Add session ID if available
        session_id = get_session_id()
        if session_id:
            default_tags["session_id"] = session_id

        if tags:
            default_tags.update(tags)

        try:
            run = mlflow.start_run(run_name=run_name, nested=nested, tags=default_tags)
            self.active_run_id = run.info.run_id

            logger.info(
                f"Started MLflow run",
                run_id=run.info.run_id,
                run_name=run_name,
            )

            yield run

        except Exception as e:
            logger.error(f"Error in MLflow run: {e}")
            if mlflow.active_run():
                mlflow.end_run(status=RunStatus.to_string(RunStatus.FAILED))
            raise

        finally:
            if mlflow.active_run():
                mlflow.end_run()
                logger.info("Ended MLflow run", run_id=self.active_run_id)
                self.active_run_id = None

    def log_params(self, params: Dict[str, Any]):
        """Log multiple parameters"""
        try:
            mlflow.log_params(params)
            logger.debug(f"Logged {len(params)} parameters")
        except Exception as e:
            logger.error(f"Failed to log params: {e}")

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log multiple metrics"""
        try:
            mlflow.log_metrics(metrics, step=step)
            logger.debug(f"Logged {len(metrics)} metrics")
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")

    def log_artifact(self, artifact_path: str, artifact_name: Optional[str] = None):
        """Log an artifact"""
        try:
            if artifact_name:
                mlflow.log_artifact(artifact_path, artifact_name)
            else:
                mlflow.log_artifact(artifact_path)
            logger.debug(f"Logged artifact: {artifact_path}")
        except Exception as e:
            logger.error(f"Failed to log artifact: {e}")

    def log_dict(self, dictionary: Dict, filename: str):
        """Log a dictionary as JSON artifact"""
        try:
            mlflow.log_dict(dictionary, filename)
            logger.debug(f"Logged dict as {filename}")
        except Exception as e:
            logger.error(f"Failed to log dict: {e}")

    def log_agent_interaction(
        self,
        agent_name: str,
        input_data: Any,
        output_data: Any,
        duration: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """
        Log an agent interaction with standard format.

        Args:
            agent_name: Name of the agent
            input_data: Input to the agent
            output_data: Output from the agent
            duration: Duration in seconds
            success: Whether the interaction was successful
            error: Optional error message
        """
        try:
            # Log as nested run
            with self.start_run(run_name=f"{agent_name}_interaction", nested=True):
                mlflow.log_params(
                    {
                        "agent_name": agent_name,
                        "success": success,
                    }
                )

                mlflow.log_metrics(
                    {
                        "duration_seconds": duration,
                    }
                )

                # Log input/output as artifacts
                mlflow.log_dict(
                    {
                        "input": str(input_data)[:10000],  # Limit size
                        "output": str(output_data)[:10000],
                        "error": error,
                    },
                    f"{agent_name}_interaction.json",
                )

                logger.info(
                    f"Logged {agent_name} interaction",
                    duration=duration,
                    success=success,
                )

        except Exception as e:
            logger.error(f"Failed to log agent interaction: {e}")

    def log_query_cache_performance(
        self,
        query: str,
        cache_hit: bool,
        similarity_score: Optional[float] = None,
        latency: float = 0.0,
    ):
        """Log cache performance metrics"""
        try:
            metrics = {
                "cache_hit": 1.0 if cache_hit else 0.0,
                "cache_latency": latency,
            }

            if similarity_score is not None:
                metrics["cache_similarity"] = similarity_score

            self.log_metrics(metrics)

            logger.debug(
                "Logged cache performance",
                cache_hit=cache_hit,
                similarity_score=similarity_score,
            )

        except Exception as e:
            logger.error(f"Failed to log cache performance: {e}")


def track_agent(agent_name: str):
    """
    Decorator to track agent execution with MLflow.

    Usage:
        @track_agent("my_agent")
        def my_agent_function(input_data):
            return output_data
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = get_mlflow_tracker()

            start_time = time.time()
            error = None
            success = False
            output_data = None

            try:
                output_data = func(*args, **kwargs)
                success = True
                return output_data

            except Exception as e:
                error = str(e)
                raise

            finally:
                duration = time.time() - start_time

                # Get input data (first arg or kwarg)
                input_data = args[0] if args else kwargs.get("input", None)

                tracker.log_agent_interaction(
                    agent_name=agent_name,
                    input_data=input_data,
                    output_data=output_data,
                    duration=duration,
                    success=success,
                    error=error,
                )

        return wrapper

    return decorator


# Global tracker instance
_mlflow_tracker = None


def get_mlflow_tracker() -> MLflowTracker:
    """Get global MLflow tracker instance"""
    global _mlflow_tracker
    if _mlflow_tracker is None:
        _mlflow_tracker = MLflowTracker()
    return _mlflow_tracker
