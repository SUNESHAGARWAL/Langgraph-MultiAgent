"""
Configuration management for Multi-Agent Orchestrator System.
Handles all environment variables and settings with validation.
"""

import os
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAIConfig(BaseSettings):
    """Azure OpenAI Configuration"""

    endpoint: str = Field(..., alias="AZURE_OPENAI_ENDPOINT")
    api_key: str = Field(..., alias="AZURE_OPENAI_API_KEY")
    api_version: str = Field(default="2024-08-01-preview", alias="AZURE_OPENAI_API_VERSION")

    gpt4o_deployment: str = Field(..., alias="AZURE_OPENAI_GPT4O_DEPLOYMENT")
    gpt4o_mini_deployment: str = Field(default="gpt-4o-mini", alias="AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT")
    embedding_deployment: str = Field(..., alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class DatabricksConfig(BaseSettings):
    """Databricks and Genie Configuration"""

    host: str = Field(..., alias="DATABRICKS_HOST")
    token: str = Field(..., alias="DATABRICKS_TOKEN")
    workspace_id: Optional[str] = Field(default=None, alias="DATABRICKS_WORKSPACE_ID")
    sql_warehouse_id: Optional[str] = Field(default=None, alias="DATABRICKS_SQL_WAREHOUSE_ID")

    genie_space_id: str = Field(..., alias="GENIE_SPACE_ID")
    genie_timeout: int = Field(default=30, alias="GENIE_TIMEOUT")

    unity_catalog: str = Field(default="main", alias="UNITY_CATALOG_NAME")
    unity_schema: str = Field(default="default", alias="UNITY_CATALOG_SCHEMA")
    unity_tables: str = Field(default="", alias="UNITY_CATALOG_TABLES")

    @field_validator("unity_tables", mode="after")
    @classmethod
    def parse_tables(cls, v):
        """Parse comma-separated table names into a list"""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [t.strip() for t in v.split(",") if t.strip()]
        elif isinstance(v, list):
            return v
        return []

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Unused config classes removed in v5.0 simplification:
# - AzureStorageConfig (not used in simplified architecture)
# - RedisConfig (not used in simplified architecture)
# - CacheConfig (not used in simplified architecture)
# - DatabaseConfig (not used in simplified architecture)
# - VectorStoreConfig (not used in simplified architecture)
# - RAGConfig (not used in simplified architecture)


class MLflowConfig(BaseSettings):
    """MLflow Configuration"""

    tracking_uri: str = Field(default="databricks", alias="MLFLOW_TRACKING_URI")
    experiment_name: str = Field(..., alias="MLFLOW_EXPERIMENT_NAME")
    tracking_enabled: bool = Field(default=True, alias="MLFLOW_TRACKING_ENABLED")
    enable_system_metrics: bool = Field(default=True, alias="MLFLOW_ENABLE_SYSTEM_METRICS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AgentConfig(BaseSettings):
    """Agent Behavior Configuration"""

    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    enable_human_in_loop: bool = Field(default=True, alias="ENABLE_HUMAN_IN_LOOP")
    enable_planning: bool = Field(default=True, alias="ENABLE_PLANNING")
    enable_feedback_loops: bool = Field(default=True, alias="ENABLE_FEEDBACK_LOOPS")

    orchestrator_max_planning_steps: int = Field(default=5, alias="ORCHESTRATOR_MAX_PLANNING_STEPS")
    orchestrator_confidence_threshold: float = Field(default=0.7, alias="ORCHESTRATOR_CONFIDENCE_THRESHOLD")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class LoggingConfig(BaseSettings):
    """Logging and Tracing Configuration"""

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    enable_tracing: bool = Field(default=True, alias="ENABLE_TRACING")
    enable_langsmith: bool = Field(default=False, alias="ENABLE_LANGSMITH")

    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_endpoint: Optional[str] = Field(default=None, alias="LANGCHAIN_ENDPOINT")
    langchain_api_key: Optional[str] = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: Optional[str] = Field(default=None, alias="LANGCHAIN_PROJECT")

    otel_endpoint: Optional[str] = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_service_name: str = Field(default="multi-agent-orchestrator", alias="OTEL_SERVICE_NAME")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppConfig(BaseSettings):
    """Application Configuration"""

    name: str = Field(default="MultiAgentOrchestrator", alias="APP_NAME")
    version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    session_storage_path: str = Field(default="./data/sessions", alias="SESSION_STORAGE_PATH")
    session_timeout_minutes: int = Field(default=30, alias="SESSION_TIMEOUT_MINUTES")

    async_workers: int = Field(default=4, alias="ASYNC_WORKERS")
    batch_size: int = Field(default=10, alias="BATCH_SIZE")
    request_timeout: int = Field(default=120, alias="REQUEST_TIMEOUT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Config:
    """
    Master Configuration Class that aggregates all sub-configurations.
    Implements singleton pattern for consistent configuration access.
    """

    _instance: Optional["Config"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # V5.0 Simplified - Only load configs that are actually used
        self.azure_openai = AzureOpenAIConfig()
        self.databricks = DatabricksConfig()
        self.mlflow = MLflowConfig()
        self.agent = AgentConfig()
        self.logging = LoggingConfig()
        self.app = AppConfig()

        self._initialized = True
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            self.app.session_storage_path,
            "./data/logs",
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.app.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.app.environment.lower() == "development"

    def get_full_table_name(self, table: str) -> str:
        """Get fully qualified table name for Unity Catalog"""
        return f"{self.databricks.unity_catalog}.{self.databricks.unity_schema}.{table}"

    @classmethod
    def get_instance(cls) -> "Config":
        """Get singleton instance of Config"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global config instance
config = Config.get_instance()
