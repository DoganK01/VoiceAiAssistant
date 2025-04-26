from datetime import datetime
from typing import List, Optional, TypedDict
import httpx
from psycopg_pool import AsyncConnectionPool

from groq import AsyncGroq
from pydantic_ai import Agent
from openai import AsyncAzureOpenAI
from pydantic import BaseModel, Field

from app.backend.agent.ai_services import TextToSpeech


class AppState(TypedDict):
    """Typed dictionary defining the structure of shared application state."""
    db_pool: AsyncConnectionPool
    groq_client: AsyncGroq
    tts_handler: TextToSpeech
    agent: Agent
    httpx_client: httpx.AsyncClient 
    openai_client: AsyncAzureOpenAI


class ConversationTurn(BaseModel):
    """Pydantic model representing a conversation turn."""
    id: Optional[int] = None
    session_id: str
    user_transcript: Optional[str] = None
    ai_response: Optional[str] = None
    user_timestamp: Optional[datetime] = None
    ai_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class HistoryItem(BaseModel):
    """Pydantic model representing a history item."""
    user_transcript: Optional[str] = None
    ai_response: Optional[str] = None
    user_timestamp: Optional[datetime] = None
    ai_timestamp: Optional[datetime] = None

class HistoryResponse(BaseModel):
    """Pydantic model representing a history response."""
    session_id: str
    history: List[HistoryItem]

class HealthCheckDetail(BaseModel):
    """Pydantic model representing health check details."""
    database_connected: bool

class HealthResponse(BaseModel):
    """Pydantic model representing a health check response."""
    status: str = Field(..., example="ok")
    timestamp: datetime
    checks: HealthCheckDetail