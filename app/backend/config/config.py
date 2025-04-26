import logging
from typing import Optional, Any

from pydantic_settings import BaseSettings
from pydantic import SecretStr, PostgresDsn, field_validator, Field


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Settings(BaseSettings):
    PG_USER: str
    PG_PASSWORD: SecretStr
    PG_HOST: str
    PG_PORT: int
    PG_DBNAME: str

    DATABASE_URL: Optional[PostgresDsn] = Field(default=None, description="Database URL for PostgreSQL")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(
        cls, 
        v: Any, 
        info
    ) -> Any:
        """
        If DATABASE_URL is supplied, use it; otherwise, if all PG_* components
        are present, build a DSN string. Otherwise, error out.
        """
        if isinstance(v, str) and v.strip():
            logger.debug("Using provided DATABASE_URL.")
            return v

        data = info.data
        user     = data.get("PG_USER")
        password = data.get("PG_PASSWORD")
        host     = data.get("PG_HOST")
        port     = data.get("PG_PORT")
        db       = data.get("PG_DBNAME")

        if all([user, password, host, port, db]):
            dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
            logger.debug("Built DATABASE_URL from components: %s", dsn)
            return dsn

        msg = (
            "Database configuration insufficient. "
            "Either set DATABASE_URL or all of PG_USER, PG_PASSWORD, "
            "PG_HOST, PG_PORT, PG_DBNAME."
        )
        logger.error(msg)
        raise ValueError(msg)


    GROQ_API_KEY: SecretStr
    OPENAI_API_KEY: SecretStr
    OPENWEATHER_API_KEY: SecretStr
    NEWS_API_KEY: SecretStr

    GROQ_STT_MODEL: str = "whisper-large-v3-turbo"
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"
    OPENAI_TTS_MODEL: str = "tts-1"
    
    AZURE_ENDPOINT: str
    AZURE_API_VERSION: str


    AZURE_GPT_ENDPOINT: str
    AZURE_GPT_API_VERSION: str
    AZURE_GPT_API_KEY: SecretStr

    APP_LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
logger.info(f"Settings loaded. Log Level: {settings.APP_LOG_LEVEL}")