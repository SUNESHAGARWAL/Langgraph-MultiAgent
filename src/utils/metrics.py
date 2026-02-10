"""
Metrics tracking for multi-agent system.

Tracks query performance, costs, agent interactions, and system health.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import threading

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""

    # Identifiers
    query_id: str
    question: str
    thread_id: str

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    # Agent calls
    supervisor_calls: int = 0
    genie_calls: int = 0
    rag_calls: int = 0
    synthesis_calls: int = 0
    grader_calls: int = 0
    human_calls: int = 0
    parallel_executions: int = 0

    # Tokens (for cost calculation)
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Cache stats
    cache_hits: int = 0
    cache_misses: int = 0

    # Status
    success: bool = False
    iterations: int = 0
    error: Optional[str] = None
    final_answer: str = ""

    # Grading
    validation_passed: int = 0
    validation_failed: int = 0
    validation_partial: int = 0

    # Versioning (NEW)
    model_version: str = "3.0.0"  # Model version used
    experiment_id: Optional[str] = None  # A/B test experiment ID

    def duration(self) -> float:
        """Calculate query duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def estimated_cost(self) -> float:
        """
        Estimate query cost in USD.

        Based on GPT-4o pricing (as of 2024):
        - Input: $0.005 per 1K tokens
        - Output: $0.015 per 1K tokens
        """
        input_cost = (self.total_input_tokens / 1000) * 0.005
        output_cost = (self.total_output_tokens / 1000) * 0.015
        return input_cost + output_cost

    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        data = asdict(self)
        data["duration"] = self.duration()
        data["estimated_cost"] = self.estimated_cost()
        data["cache_hit_rate"] = self.cache_hit_rate()
        return data


class MetricsTracker:
    """Thread-safe metrics tracker for multi-agent system."""

    def __init__(self):
        """Initialize metrics tracker."""
        self._metrics_store: Dict[str, QueryMetrics] = {}
        self._lock = threading.Lock()

        # Aggregate stats
        self._total_queries = 0
        self._total_successful = 0
        self._total_failed = 0
        self._total_cost = 0.0
        self._total_duration = 0.0

        logger.info("Initialized MetricsTracker")

    def start_query(
        self,
        query_id: str,
        question: str,
        thread_id: str,
        model_version: str = "3.0.0",
        experiment_id: Optional[str] = None
    ) -> QueryMetrics:
        """
        Start tracking a new query.

        Args:
            query_id: Unique query identifier
            question: User question
            thread_id: Conversation thread ID
            model_version: Model version used (for A/B testing)
            experiment_id: Optional experiment ID (for A/B testing)

        Returns:
            QueryMetrics instance
        """
        with self._lock:
            metrics = QueryMetrics(
                query_id=query_id,
                question=question,
                thread_id=thread_id,
                start_time=time.time(),
                model_version=model_version,
                experiment_id=experiment_id
            )

            self._metrics_store[query_id] = metrics
            self._total_queries += 1

            logger.debug(f"Started tracking query: {query_id} (version={model_version})")

            return metrics

    def track_agent_call(
        self,
        query_id: str,
        agent_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0
    ):
        """
        Track an agent call.

        Args:
            query_id: Query identifier
            agent_name: Name of agent called
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        with self._lock:
            metrics = self._metrics_store.get(query_id)
            if not metrics:
                logger.warning(f"Query {query_id} not found in metrics store")
                return

            # Increment agent call count
            if agent_name == "supervisor":
                metrics.supervisor_calls += 1
            elif agent_name == "SQL_Specialist":
                metrics.genie_calls += 1
            elif agent_name == "document_search":
                metrics.rag_calls += 1
            elif agent_name == "synthesis":
                metrics.synthesis_calls += 1
            elif agent_name == "grader":
                metrics.grader_calls += 1
            elif agent_name == "human":
                metrics.human_calls += 1
            elif agent_name == "parallel":
                metrics.parallel_executions += 1

            # Track tokens
            metrics.total_input_tokens += input_tokens
            metrics.total_output_tokens += output_tokens

    def track_cache_hit(self, query_id: str):
        """Track a cache hit."""
        with self._lock:
            metrics = self._metrics_store.get(query_id)
            if metrics:
                metrics.cache_hits += 1

    def track_cache_miss(self, query_id: str):
        """Track a cache miss."""
        with self._lock:
            metrics = self._metrics_store.get(query_id)
            if metrics:
                metrics.cache_misses += 1

    def track_validation(
        self,
        query_id: str,
        result: str  # "RELEVANT", "PARTIAL", "NOT_RELEVANT"
    ):
        """
        Track result validation.

        Args:
            query_id: Query identifier
            result: Validation result
        """
        with self._lock:
            metrics = self._metrics_store.get(query_id)
            if not metrics:
                return

            if result == "RELEVANT":
                metrics.validation_passed += 1
            elif result == "PARTIAL":
                metrics.validation_partial += 1
            else:
                metrics.validation_failed += 1

    def end_query(
        self,
        query_id: str,
        success: bool,
        iterations: int,
        final_answer: str = "",
        error: Optional[str] = None
    ) -> QueryMetrics:
        """
        End query tracking.

        Args:
            query_id: Query identifier
            success: Whether query succeeded
            iterations: Number of iterations
            final_answer: Final answer generated
            error: Error message if failed

        Returns:
            QueryMetrics instance
        """
        with self._lock:
            metrics = self._metrics_store.get(query_id)
            if not metrics:
                logger.warning(f"Query {query_id} not found in metrics store")
                return None

            metrics.end_time = time.time()
            metrics.success = success
            metrics.iterations = iterations
            metrics.final_answer = final_answer
            metrics.error = error

            # Update aggregate stats
            if success:
                self._total_successful += 1
            else:
                self._total_failed += 1

            self._total_cost += metrics.estimated_cost()
            self._total_duration += metrics.duration()

            # Log summary
            logger.info(
                f"Query completed: {query_id}",
                extra={
                    "query_id": query_id,
                    "success": success,
                    "duration": f"{metrics.duration():.2f}s",
                    "cost": f"${metrics.estimated_cost():.4f}",
                    "iterations": iterations,
                    "supervisor_calls": metrics.supervisor_calls,
                    "genie_calls": metrics.genie_calls,
                    "rag_calls": metrics.rag_calls,
                    "cache_hits": metrics.cache_hits,
                    "cache_misses": metrics.cache_misses,
                    "cache_hit_rate": f"{metrics.cache_hit_rate():.2%}",
                }
            )

            return metrics

    def get_query_metrics(self, query_id: str) -> Optional[QueryMetrics]:
        """Get metrics for a specific query."""
        with self._lock:
            return self._metrics_store.get(query_id)

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all queries."""
        with self._lock:
            avg_duration = (
                self._total_duration / self._total_queries
                if self._total_queries > 0
                else 0.0
            )

            avg_cost = (
                self._total_cost / self._total_queries
                if self._total_queries > 0
                else 0.0
            )

            success_rate = (
                self._total_successful / self._total_queries
                if self._total_queries > 0
                else 0.0
            )

            return {
                "total_queries": self._total_queries,
                "successful": self._total_successful,
                "failed": self._total_failed,
                "success_rate": success_rate,
                "total_cost": self._total_cost,
                "average_cost": avg_cost,
                "total_duration": self._total_duration,
                "average_duration": avg_duration,
            }

    def get_recent_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent query metrics."""
        with self._lock:
            # Sort by start time descending
            sorted_metrics = sorted(
                self._metrics_store.values(),
                key=lambda m: m.start_time,
                reverse=True
            )

            return [m.to_dict() for m in sorted_metrics[:limit]]

    def clear(self):
        """Clear all metrics."""
        with self._lock:
            self._metrics_store.clear()
            self._total_queries = 0
            self._total_successful = 0
            self._total_failed = 0
            self._total_cost = 0.0
            self._total_duration = 0.0

            logger.info("Metrics cleared")


# Global singleton
_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Get or create global metrics tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = MetricsTracker()
    return _tracker
