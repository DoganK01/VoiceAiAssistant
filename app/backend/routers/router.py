import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List
import datetime
import httpx

from pydantic_ai import Agent
from psycopg_pool import AsyncConnectionPool
from groq import AsyncGroq

from app.backend.agent.ai_services import TextToSpeech
from app.backend.database.database import get_history_turns, check_pool_connection
from app.backend.schemas import HistoryItem, HealthCheckDetail, HealthResponse, HistoryResponse, ConversationTurn
from app.backend.dependencies import get_db_pool, get_groq_client, get_tts_handler, get_agent, get_httpx_client


logger = logging.getLogger(__name__)

router = APIRouter()

@router.get(
    "/history/{session_id}",
    response_model=HistoryResponse,
    summary="Get Conversation History",
    description="Retrieves the recent conversation history for a given session ID."
)
async def read_history(
    session_id: str,
    db_pool: AsyncConnectionPool = Depends(get_db_pool)
):
    try:
        history_turns: List[ConversationTurn] = await get_history_turns(db_pool, session_id)

        api_history_items: List[HistoryItem] = [
            HistoryItem(
                user_transcript=turn.user_transcript,
                ai_response=turn.ai_response,
                user_timestamp=turn.user_timestamp,
                ai_timestamp=turn.ai_timestamp
            ) for turn in history_turns if turn.created_at
        ]
        return HistoryResponse(session_id=session_id, history=api_history_items)
    except Exception as e:
        logger.error(f"API error retrieving history for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve history")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Performs health checks on database and AI service connectivity."
)
async def health_check(
     db_pool: AsyncConnectionPool = Depends(get_db_pool),
     groq_client: AsyncGroq = Depends(get_groq_client),
     tts_handler: TextToSpeech = Depends(get_tts_handler),
     agent: Agent = Depends(get_agent),
     httpx_client: httpx.AsyncClient = Depends(get_httpx_client)
):
    db_ok = await check_pool_connection(db_pool)

    status = "ok" if db_ok else "partial_error"
    response_data = HealthResponse(
        status=status,
        timestamp=datetime.datetime.utcnow(),
        checks=HealthCheckDetail(
            database_connected=db_ok,
        )
    )
    if status != "ok":
         raise HTTPException(status_code=503, detail=response_data.model_dump())

    return response_data
