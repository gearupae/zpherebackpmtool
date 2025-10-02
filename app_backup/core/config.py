from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Zphere"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./zphere.db"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "zphere_db"
    DATABASE_USER: str = ""
    DATABASE_PASSWORD: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "your-super-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_dummy"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_dummy"
    STRIPE_WEBHOOK_SECRET: str = "whsec_dummy"
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads/"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
