"""
Configuration management for the AI Research Project.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """
    Configuration class for the AI Research Project.
    """
    
    # Required Configuration
    openai_api_key: str
    milvus_host: str
    milvus_token: str
    
    # OpenAI Configuration
    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-4o-mini"
    openai_max_retries: int = 3
    openai_retry_delay: float = 1.0
    
    # Milvus Configuration
    milvus_collection_name: str = "pdf_documents"
    
    # Vector Search Configuration
    vector_search_max_results: int = 5
    vector_search_similarity_threshold: float = 0.7
    vector_search_max_context_length: int = 4000
    
    # Embedding Configuration
    embedding_batch_size: int = 100
    embedding_max_tokens: int = 8191
    
    # Web Search Configuration (for future use)
    web_search_enabled: bool = True
    web_search_max_results: int = 5
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Application Configuration
    app_name: str = "AI Research Project"
    app_version: str = "0.1.0"
    environment: str = "development"
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Create configuration from environment variables.
        
        Returns:
            Config instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # Required environment variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        milvus_host = os.getenv("ZILLIZ_HOST")
        milvus_token = os.getenv("ZILLIZ_TOKEN")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not milvus_host:
            raise ValueError("ZILLIZ_HOST environment variable is required")
        if not milvus_token:
            raise ValueError("ZILLIZ_TOKEN environment variable is required")
            
        return cls(
            # OpenAI Configuration
            openai_api_key=openai_api_key,
            openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            openai_max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
            openai_retry_delay=float(os.getenv("OPENAI_RETRY_DELAY", "1.0")),
            
            # Milvus Configuration
            milvus_host=milvus_host,
            milvus_token=milvus_token,
            milvus_collection_name=os.getenv("MILVUS_COLLECTION_NAME", "pdf_documents"),
            
            # Vector Search Configuration
            vector_search_max_results=int(os.getenv("VECTOR_SEARCH_MAX_RESULTS", "5")),
            vector_search_similarity_threshold=float(os.getenv("VECTOR_SEARCH_SIMILARITY_THRESHOLD", "0.7")),
            vector_search_max_context_length=int(os.getenv("VECTOR_SEARCH_MAX_CONTEXT_LENGTH", "4000")),
            
            # Embedding Configuration
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "100")),
            embedding_max_tokens=int(os.getenv("EMBEDDING_MAX_TOKENS", "8191")),
            
            # Web Search Configuration
            web_search_enabled=os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true",
            web_search_max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")),
            
            # Logging Configuration
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            
            # Application Configuration
            app_name=os.getenv("APP_NAME", "AI Research Project"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            environment=os.getenv("ENVIRONMENT", "development")
        )
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            "openai": {
                "embedding_model": self.openai_embedding_model,
                "chat_model": self.openai_chat_model,
                "max_retries": self.openai_max_retries,
                "retry_delay": self.openai_retry_delay
            },
            "milvus": {
                "host": self.milvus_host,
                "collection_name": self.milvus_collection_name
            },
            "vector_search": {
                "max_results": self.vector_search_max_results,
                "similarity_threshold": self.vector_search_similarity_threshold,
                "max_context_length": self.vector_search_max_context_length
            },
            "embedding": {
                "batch_size": self.embedding_batch_size,
                "max_tokens": self.embedding_max_tokens
            },
            "web_search": {
                "enabled": self.web_search_enabled,
                "max_results": self.web_search_max_results
            },
            "logging": {
                "level": self.log_level,
                "format": self.log_format
            },
            "app": {
                "name": self.app_name,
                "version": self.app_version,
                "environment": self.environment
            }
        }
        
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
        
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """
    Reload configuration from environment variables.
    
    Returns:
        New Config instance
    """
    global _config
    load_dotenv()  # Reload .env file
    _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """
    Set the global configuration instance.
    
    Args:
        config: Configuration instance to set
    """
    global _config
    _config = config