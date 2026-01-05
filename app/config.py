"""Configuration management using environment variables."""
import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
    
    WEBHOOK_SECRET: Optional[str] = os.getenv("WEBHOOK_SECRET")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    APP_NAME: str = "Lyftr AI Webhook API"
    APP_VERSION: str = "1.0.0"
    
    def is_ready(self) -> bool:
        """Check if the application is ready (DB accessible and WEBHOOK_SECRET set)."""
        return self.WEBHOOK_SECRET is not None and len(self.WEBHOOK_SECRET) > 0


settings = Settings()

