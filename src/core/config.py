"""
Configuration management for Zero-A2A
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Server settings
    app_name: str = "Zero-A2A Enterprise Agent"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Security settings
    jwt_secret_key: str = Field(default="development-secret-key-change-in-production", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="RS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    
    # Database settings
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/zero_a2a",
        env="DATABASE_URL"
    )
    database_pool_min_size: int = Field(default=5, env="DATABASE_POOL_MIN_SIZE")
    database_pool_max_size: int = Field(default=20, env="DATABASE_POOL_MAX_SIZE")
    
    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    redis_pool_min_size: int = Field(default=5, env="REDIS_POOL_MIN_SIZE")
    redis_pool_max_size: int = Field(default=20, env="REDIS_POOL_MAX_SIZE")
    
    # External API settings
    weather_api_key: Optional[str] = Field(None, env="WEATHER_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    
    # Monitoring settings
    prometheus_port: int = Field(default=8090, env="PROMETHEUS_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    
    # A2A Protocol settings
    agent_timeout: int = Field(default=300, env="AGENT_TIMEOUT")
    max_concurrent_tasks: int = Field(default=100, env="MAX_CONCURRENT_TASKS")
    enable_streaming: bool = Field(default=True, env="ENABLE_STREAMING")
    enable_push_notifications: bool = Field(default=True, env="ENABLE_PUSH_NOTIFICATIONS")
    
    # Rate limiting settings
    rate_limit_rpm: int = Field(default=100, env="RATE_LIMIT_RPM")
    rate_limit_burst: int = Field(default=20, env="RATE_LIMIT_BURST")
    
    # Security settings
    enable_cors: bool = Field(default=True, env="ENABLE_CORS")
    enable_security_headers: bool = Field(default=True, env="ENABLE_SECURITY_HEADERS")
    max_request_size: int = Field(default=10485760, env="MAX_REQUEST_SIZE")  # 10MB
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
