"""Configuration settings for Bank Research Gateway."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class GatewayConfig:
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    qdrant_url: str = os.getenv("QDRANT_URL", ":memory:")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = GatewayConfig()
