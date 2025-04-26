from psycopg_pool import AsyncConnectionPool
from typing import Optional
from httpx import AsyncClient
import httpx

from groq import AsyncGroq
from openai import AsyncAzureOpenAI

from app.backend.config.config import settings, logger

def create_groq_client() -> Optional[AsyncGroq]:
    """Creates and returns an AsyncGroq client instance."""
    if settings.GROQ_API_KEY:
        try:
            client = AsyncGroq(api_key=settings.GROQ_API_KEY.get_secret_value())
            logger.info("AsyncGroq client created.")
            return client
        except Exception as e:
            logger.error(f"Failed to create AsyncGroq client: {e}", exc_info=True)
            return None
    else:
        logger.warning("Groq API key not set. Cannot create Groq client.")
        return None

def create_db_pool() -> Optional[AsyncConnectionPool]:
    """Creates and returns an AsyncConnectionPool instance."""
    if not all([settings.PG_USER, settings.PG_PASSWORD, settings.PG_HOST, settings.PG_DBNAME]):
         logger.error("Database configuration components missing. Cannot create pool.")
         return None
    try:
        conninfo = f"""
            user={settings.PG_USER}
            password={settings.PG_PASSWORD.get_secret_value()}
            host={settings.PG_HOST}
            port={settings.PG_PORT}
            dbname={settings.PG_DBNAME}
        """
        pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=2,
            max_size=10,
        )
        logger.info("AsyncConnectionPool created.")
        return pool
    except Exception as e:
        logger.error(f"Failed to create AsyncConnectionPool: {e}", exc_info=True)
        return None
    

def create_httpx_session() -> AsyncClient:
    """
    Creates a client session for making HTTP requests asynchronously.

    Returns:
        Client session for making HTTP requests asynchronously.
    """
    timeout = httpx.Timeout(10.0, connect=5.0) 
    client = AsyncClient(timeout=timeout, follow_redirects=True)
    logger.info("HTTPX client session created.")
    return client

def create_openai_client() -> Optional[AsyncAzureOpenAI]:
    """Creates and returns an AsyncAzureOpenAI client instance."""
    if settings.PG_USER:
        try:
            client = AsyncAzureOpenAI(
                api_key=settings.OPENAI_API_KEY.get_secret_value(),
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
            )
            logger.info("AsyncAzureOpenAI client created.")
            return client
        except Exception as e:
            logger.error(f"Failed to create AsyncAzureOpenAI client: {e}", exc_info=True)
            return None
    else:
        logger.warning("OpenAI API key not set. Cannot create OpenAI client.")
        return None