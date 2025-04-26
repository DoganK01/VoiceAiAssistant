import logging
from typing import Optional
from psycopg_pool import AsyncConnectionPool

from groq import AsyncGroq
from pydantic_ai import Agent
from fastapi import WebSocket

from app.backend.schemas import ConversationTurn
from app.backend.agent.utils import format_messages_for_agent, parse_agent_result
from app.backend.agent.ai_services import TextToSpeech
from app.backend.agent.agent import AgentDependencies
from app.backend.database.database import add_conversation_turn, get_history_turns
from app.backend.agent.ai_services import speech_to_text, stream_tts


logger = logging.getLogger(__name__)

class VoicePipelineError(Exception):
    """Custom exception for pipeline failures."""
    def __init__(self, message: str, step: str):
        self.message = message
        self.step = step
        super().__init__(f"Pipeline error at step '{step}': {message}")


async def process_voice_interaction(
    websocket: WebSocket,
    agent: Agent[AgentDependencies],
    deps: AgentDependencies,
    session_id: str,
    audio_bytes: bytes,
    db_pool: AsyncConnectionPool,
    groq_ai_client: AsyncGroq,
    tts_handler: TextToSpeech
) -> Optional[ConversationTurn]:
    """Orchestrates the STT -> LLM -> TTS -> DB pipeline using provided resources."""

    logger.info(f"Starting voice pipeline for session {session_id}")

    user_transcript = await speech_to_text(groq_ai_client, audio_bytes)
    if user_transcript is None:
        raise VoicePipelineError("Failed to transcribe audio.", step="stt")
    logger.info(f"STT Result for {session_id}: {user_transcript}")

    history = await get_history_turns(db_pool, session_id)

    agent_messages = format_messages_for_agent(history)

    full_response, agent_new_messages = await stream_tts(websocket=websocket,
                                                  agent=agent,
                                                  tts_handler=tts_handler,
                                                  user_prompt=user_transcript,
                                                  message_history=agent_messages,
                                                  deps=deps)
    


    if full_response is None:
        raise VoicePipelineError("Failed to synthesize speech.", step="tts")
    logger.info(f"TTS Result for {session_id} successfull !!")

    (user_timestamp_this_turn,
    ai_timestamp_this_turn) = parse_agent_result(agent_new_messages)

    logger.info(f"Timestamps extracted: User={user_timestamp_this_turn}, AI={ai_timestamp_this_turn}")

    saved_turn = await add_conversation_turn(
        pool_or_conn=db_pool,
        session_id=session_id,
        user_transcript=user_transcript,
        ai_response=full_response,
        user_timestamp=user_timestamp_this_turn,
        ai_timestamp=ai_timestamp_this_turn
    )
    if saved_turn is None:
        logger.error(f"Failed to save conversation turn for session {session_id}, proceeding.")
        saved_turn = ConversationTurn(
             session_id=session_id, user_transcript=user_transcript, ai_response=full_response,
             user_timestamp=user_timestamp_this_turn, ai_timestamp=ai_timestamp_this_turn
        )

    logger.info(f"Voice pipeline completed successfully for session {session_id}")
    return saved_turn