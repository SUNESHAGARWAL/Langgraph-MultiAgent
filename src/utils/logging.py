"""
Comprehensive logging and tracing utilities with OpenTelemetry support.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps
import traceback

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from src.core.config import config

# Context variables for tracing
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add session and request IDs if available
        session_id = session_id_var.get()
        if session_id:
            log_data["session_id"] = session_id

        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data)


class StructuredLogger:
    """
    Structured logger with context awareness and extra data support.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_logger()

    def _setup_logger(self):
        """Setup logger with appropriate handlers and formatters"""
        if self.logger.handlers:
            return  # Already configured

        self.logger.setLevel(getattr(logging, config.logging.log_level.upper()))
        self.logger.propagate = False

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)

        if config.logging.log_format == "json":
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )

        self.logger.addHandler(console_handler)

    def _log(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Internal logging method with extra data support"""
        record = self.logger.makeRecord(
            self.logger.name,
            getattr(logging, level.upper()),
            "(unknown file)",
            0,
            message,
            (),
            None,
        )

        if extra_data:
            record.extra_data = extra_data

        self.logger.handle(record)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log("DEBUG", message, kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log("INFO", message, kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log("WARNING", message, kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log("ERROR", message, kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log("CRITICAL", message, kwargs)

    def exception(self, message: str, exc_info=True, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, exc_info=exc_info, extra={"extra_data": kwargs})


class TracingManager:
    """
    OpenTelemetry tracing manager for distributed tracing.
    """

    _instance: Optional["TracingManager"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if config.logging.enable_tracing:
            self._setup_tracing()

        self._initialized = True

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing"""
        resource = Resource.create(
            {
                "service.name": config.logging.otel_service_name,
                "service.version": config.app.version,
                "deployment.environment": config.app.environment,
            }
        )

        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint is configured
        if config.logging.otel_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=config.logging.otel_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        else:
            # Fallback to console exporter for development
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))

        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(__name__)

    def get_tracer(self):
        """Get OpenTelemetry tracer"""
        if config.logging.enable_tracing:
            return self.tracer
        return None


# Global tracing manager
tracing_manager = TracingManager()


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


def trace_function(span_name: Optional[str] = None):
    """
    Decorator for tracing function execution with OpenTelemetry.

    Args:
        span_name: Optional custom span name (defaults to function name)

    Usage:
        @trace_function("my_custom_span")
        def my_function():
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.logging.enable_tracing:
                return func(*args, **kwargs)

            tracer = tracing_manager.get_tracer()
            if not tracer:
                return func(*args, **kwargs)

            span_name_final = span_name or func.__name__

            with tracer.start_as_current_span(span_name_final) as span:
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                # Add session and request IDs
                session_id = session_id_var.get()
                if session_id:
                    span.set_attribute("session.id", session_id)

                request_id = request_id_var.get()
                if request_id:
                    span.set_attribute("request.id", request_id)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


def set_session_id(session_id: str):
    """Set session ID for current context"""
    session_id_var.set(session_id)


def set_request_id(request_id: str):
    """Set request ID for current context"""
    request_id_var.set(request_id)


def get_session_id() -> Optional[str]:
    """Get session ID from current context"""
    return session_id_var.get()


def get_request_id() -> Optional[str]:
    """Get request ID from current context"""
    return request_id_var.get()


# Setup LangChain callbacks if LangSmith is enabled
if config.logging.enable_langsmith:
    import os

    os.environ["LANGCHAIN_TRACING_V2"] = str(config.logging.langchain_tracing_v2).lower()
    if config.logging.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = config.logging.langchain_endpoint
    if config.logging.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = config.logging.langchain_api_key
    if config.logging.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = config.logging.langchain_project
