import logging
from fastapi import WebSocket, WebSocketDisconnect

from psycopg_pool import AsyncConnectionPool
from groq import AsyncGroq
from pydantic_ai import Agent

from app.backend.agent.ai_services import TextToSpeech
from app.backend.agent.agent import AgentDependencies
from app.backend.services import process_voice_interaction, VoicePipelineError


logger = logging.getLogger(__name__)


async def send_websocket_message(websocket: WebSocket, message: str):
    """Safely sends a text message over the WebSocket."""
    try:
        await websocket.send_text(message)
    except Exception as e:
        logger.warning(f"Failed to send WebSocket message '{message[:30]}...': {e}")


async def handle_websocket_connection(
    websocket: WebSocket,
    agent: Agent[AgentDependencies],
    deps: AgentDependencies,
    session_id: str,
    db_pool: AsyncConnectionPool,
    groq_ai_client: AsyncGroq,
    tts_handler: TextToSpeech):
    """
    Manages WebSocket connection.
    Uses iter_bytes() to receive complete audio messages from the client.
    Processes each audio message immediately through the AI pipeline.
    """
    await websocket.accept()
    logger.info(f"WebSocket accepted for session: {session_id}")

    await send_websocket_message(websocket, "STATUS: Ready")

    try:
        async for full_audio_bytes in websocket.iter_bytes():
            if not full_audio_bytes:
                logger.warning(f"Received empty bytes message for session {session_id}. Ignoring.")
                continue

            logger.info(f"Received complete audio message ({len(full_audio_bytes)} bytes) for session {session_id}. Processing...")
            try:
                await send_websocket_message(websocket, "STATUS: Processing...")
                saved_turn= await process_voice_interaction(
                    websocket=websocket,
                    agent=agent,
                    deps=deps,
                    session_id=session_id,
                    audio_bytes=full_audio_bytes,
                    db_pool=db_pool,
                    groq_ai_client=groq_ai_client,
                    tts_handler=tts_handler,
                )
                if saved_turn and saved_turn.user_transcript:
                     await send_websocket_message(websocket, f"USER_TRANSCRIPT: {saved_turn.user_transcript}")
                if saved_turn and saved_turn.ai_response:
                     await send_websocket_message(websocket, f"AI_RESPONSE: {saved_turn.ai_response}")
                else:
                    await send_websocket_message(websocket, "ERROR: Failed to generate audio response.")

            except VoicePipelineError as e:
                logger.error(f"Pipeline error for session {session_id}: Step='{e.step}', Message='{e.message}'")
                await send_websocket_message(websocket, f"ERROR: {e.message} (step: {e.step})")
            except Exception as e:
                logger.error(f"Unexpected error processing audio stream for session {session_id}: {e}", exc_info=True)
                await send_websocket_message(websocket, "ERROR: An unexpected server error occurred during processing.")
            finally:
                 await send_websocket_message(websocket, "STATUS: Ready")

    except WebSocketDisconnect as e:
        logger.info(f"WebSocket disconnected for session: {session_id}. Code: {e.code}, Reason: {e.reason}")
    except RuntimeError as e:
         if "connection closed" in str(e).lower():
              logger.warning(f"WebSocket connection closed abruptly for session {session_id}.")
         else:
              logger.error(f"Runtime error in WebSocket handler for session {session_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        logger.info(f"Cleaned up resources for WebSocket session: {session_id}")

