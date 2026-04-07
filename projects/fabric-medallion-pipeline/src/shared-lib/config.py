"""
Shared configuration models for Fabric Medallion Pipeline.
Loads from environment variables with secure Azure Key Vault integration.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StorageConfig:
    account_name: str
    container_name: str
    bronze_path: str = "bronze"
    silver_path: str = "silver"
    gold_path: str = "gold"

    @classmethod
    def from_env(cls) -> "StorageConfig":
        return cls(
            account_name=os.environ["ADLS_ACCOUNT_NAME"],
            container_name=os.environ.get("ADLS_CONTAINER", "medallion"),
        )


@dataclass
class SnowflakeConfig:
    account: str
    database: str
    schema: str
    table: str
    mirror_file_path: Optional[str] = None

    @classmethod
    def from_env(cls) -> "SnowflakeConfig":
        return cls(
            account=os.environ.get("SNOWFLAKE_ACCOUNT", ""),
            database=os.environ.get("SNOWFLAKE_DATABASE", ""),
            schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
            table=os.environ.get("SNOWFLAKE_TABLE", "events"),
            mirror_file_path=os.environ.get("SNOWFLAKE_MIRROR_PATH"),
        )


@dataclass
class ObservabilityConfig:
    app_insights_connection_string: Optional[str] = None
    log_analytics_workspace_id: Optional[str] = None
    structured_log_path: str = "logs/events.jsonl"

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        return cls(
            app_insights_connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            log_analytics_workspace_id=os.environ.get("LOG_ANALYTICS_WORKSPACE_ID"),
        )


@dataclass
class ResilienceConfig:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    timeout_seconds: float = 60.0
    circuit_breaker_threshold: int = 5

    @classmethod
    def from_env(cls) -> "ResilienceConfig":
        return cls(
            max_retries=int(os.environ.get("PIPELINE_MAX_RETRIES", "3")),
            base_delay_seconds=float(os.environ.get("PIPELINE_BASE_DELAY", "1.0")),
            timeout_seconds=float(os.environ.get("PIPELINE_TIMEOUT_SECONDS", "60.0")),
        )


@dataclass
class PipelineConfig:
    environment: str
    azure_region: str
    storage: StorageConfig = field(default_factory=lambda: StorageConfig("", ""))
    snowflake: SnowflakeConfig = field(default_factory=lambda: SnowflakeConfig("", "", "", ""))
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    mode: str = "live"  # "live" | "sample"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            environment=os.environ.get("AZURE_ENV", "dev"),
            azure_region=os.environ.get("AZURE_REGION", "eastus"),
            storage=StorageConfig.from_env(),
            snowflake=SnowflakeConfig.from_env(),
            observability=ObservabilityConfig.from_env(),
            resilience=ResilienceConfig.from_env(),
            mode=os.environ.get("PIPELINE_MODE", "live"),
        )
