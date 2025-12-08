from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class DatabaseSettings(BaseSettings):
    # Support both POSTGRES_* and standard PG* env vars (common in Railway/Render)
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    
    # Fallback/Alternatives
    PGHOST: Optional[str] = None
    PGPORT: Optional[int] = None
    PGUSER: Optional[str] = None
    PGPASSWORD: Optional[str] = None
    PGDATABASE: Optional[str] = None
    
    DATABASE_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file="./.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    
    @property
    def POSTGRES_URL(self):
        # 1. Prefer DATABASE_URL if available
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Fix scheme for asyncpg
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # Remove any existing sslmode params to ensure our custom SSL context takes precedence
            # and avoids conflicts or double-ssl-wrapping issues
            if "?" in url:
                base_url, query = url.split("?", 1)
                # Filter out sslmode
                params = [p for p in query.split("&") if not p.startswith("sslmode=")]
                if params:
                    url = f"{base_url}?{'&'.join(params)}"
                else:
                    url = base_url
                    
            return url
            
        # 2. Construct from components (check both POSTGRES_* and PG*)
        host = self.POSTGRES_SERVER or self.PGHOST
        port = self.POSTGRES_PORT or self.PGPORT
        user = self.POSTGRES_USER or self.PGUSER
        password = self.POSTGRES_PASSWORD or self.PGPASSWORD
        db = self.POSTGRES_DB or self.PGDATABASE
        
        if host and user and db:
             return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
        
        # Default fallback (might fail if env vars missing)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = DatabaseSettings()