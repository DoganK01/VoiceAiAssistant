from fastapi import HTTPException, status, Depends
from typing import cast
import httpx
from starlette.requests import HTTPConnection

from psycopg_pool import AsyncConnectionPool
from groq import AsyncGroq
from pydantic_ai import Agent

from app.backend.agent.ai_services import TextToSpeech
from app.backend.schemas import AppState
from app.backend.agent.agent import AgentDependencies
from app.backend.config.config import settings


def get_app_state(request: HTTPConnection) -> AppState:
    """Retrieves the shared application state dictionary."""
    state = getattr(request.app.state, "shared_state", None)
    if not state or not isinstance(state, dict):
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="Application state not initialized."
         )
    return cast(AppState, state)

def get_db_pool(state: AppState = Depends(get_app_state)) -> AsyncConnectionPool:
    """Dependency to get the Database Connection Pool from app state."""
    pool = state.get("db_pool")
    if pool is None:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="Database pool not available in state."
         )
    return pool

def get_groq_client(state: AppState = Depends(get_app_state)) -> AsyncGroq:
    """Dependency to get the AsyncGroq client from app state."""
    client = state.get("groq_client")
    if client is None:
          raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="Groq client not available in state."
         )
    return client

def get_tts_handler(state: AppState = Depends(get_app_state)) -> TextToSpeech:
    """Dependency to get the OpenAI client from app state."""
    client = state.get("tts_handler")
    if client is None:
          raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="OpenAI client not available in state."
         )
    return client


def get_agent(state: AppState = Depends(get_app_state)) -> Agent:
    """Dependency to get the Groq agent from app state."""
    agent = state.get("agent")
    if agent is None:
          raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="Groq agent not available in state."
         )
    return agent

def get_httpx_client(state: AppState = Depends(get_app_state)) -> httpx.AsyncClient:
    """Dependency to get the HTTPX client from app state."""
    client = state.get("httpx_client")
    if client is None:
          raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="HTTPX client not available in state."
         )
    return client

def get_dependencies(state: AppState = Depends(get_app_state)) -> AgentDependencies:
    """Dependency to get the AgentDependencies from app state."""
    return AgentDependencies(
        settings=settings,
        session=state.get("httpx_client"),
    )
