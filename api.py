import logging
from fastapi import FastAPI, WebSocket, Depends
from contextlib import asynccontextmanager
from typing import AsyncIterator
import asyncio
import httpx
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

from pydantic_ai import Agent, Tool
from groq import AsyncGroq
from openai import AsyncAzureOpenAI

from app.backend.routers import router as api_router
from app.backend.api.websocket_manager import handle_websocket_connection
from app.backend.schemas import AppState
from app.backend.factories import create_db_pool, create_groq_client, create_openai_client, create_httpx_session
from app.backend.dependencies import get_db_pool, get_groq_client, get_tts_handler, get_agent, get_dependencies
from app.backend.agent.agent import create_groq_model, create_groq_agent, AgentDependencies, create_openai_agent, create_openai_client_gpt, create_openi_model
from app.backend.agent.tools import get_latest_news, get_weather
from app.backend.agent.ai_services import TextToSpeech
from app.backend.database.database import create_conversations_table


SYSTEM_PROMOT = """
You are a helpful assistant. You can answer questions, provide information, and assist with tasks.
You can also access external tools to get information or perform actions.
You can use the following tools:

    1. "get_weather": Provides current weather information.

    2. "get_latest_news": Provides the latest news.
"""

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[AppState]:
    logger.info("Application starting up...")
    db_pool = create_db_pool()
    open_client_gpt = create_openai_client_gpt()
    groq_client = create_groq_client()
    openai_client = create_openai_client()
    _openai_model = create_openi_model(openai_client=open_client_gpt)
    httpx_client = create_httpx_session()
    agent = create_openai_agent(openai_model=_openai_model,
                              tools=[
                                  Tool(function=get_weather, takes_ctx=True, description="Get weather information"),
                                  Tool(function=get_latest_news, takes_ctx=True, description="Get latest news"),
                              ],
                              system_prompt=SYSTEM_PROMOT,
                            )
    tts_handler = TextToSpeech(client=openai_client)

    if not db_pool: raise RuntimeError("Database pool could not be created.")
    if not groq_client: raise RuntimeError("Groq client could not be created.")
    if not open_client_gpt: raise RuntimeError("OpenAI client GPT could not be created.")
    if not tts_handler: raise RuntimeError("OpenAI client could not be created.")
    if not agent: raise RuntimeError("Agent could not be created.")
    if not httpx_client: raise RuntimeError("HTTPX client could not be created.")
    

    logger.info("Opening database connection pool...")
    await db_pool.open()
    await create_conversations_table(db_pool)

    state: AppState = {
        "db_pool": db_pool,
        "groq_client": groq_client,
        "tts_handler": tts_handler,
        "agent": agent,
        "httpx_client": httpx_client,
        "openai_client": openai_client,
    }
    app.state.shared_state = state
    logger.info("Application state initialized and stored.")

    try:
        yield state
    finally:
        logger.info("Application shutting down...")
        shared_state_dict = getattr(app.state, 'shared_state', {})
        pool_to_close = shared_state_dict.get('db_pool')
        groq_client_to_close = shared_state_dict.get('groq_client')
        openai_client_to_close = shared_state_dict.get('openai_client')
        httpx_client_to_close = shared_state_dict.get('httpx_client')

        if httpx_client_to_close and isinstance(httpx_client_to_close, httpx.AsyncClient):
            logger.info("Closing httpx client...")
            try:
                await httpx_client_to_close.aclose()
            except Exception as e:
                logger.error(f"Error closing httpx client: {e}", exc_info=True)

        if openai_client_to_close and isinstance(openai_client_to_close, AsyncAzureOpenAI):
            logger.info("Closing OpenAI client...")
            try:
                await openai_client_to_close.close()
            except Exception as e:
                logger.error(f"Error closing OpenAI client: {e}", exc_info=True)

        if groq_client_to_close and hasattr(groq_client_to_close, 'close') and asyncio.iscoroutinefunction(groq_client_to_close.close):
             logger.info("Closing Groq client...")
             try:
                 await groq_client_to_close.close()
             except Exception as e:
                 logger.error(f"Error closing Groq client: {e}", exc_info=True)


        if pool_to_close and isinstance(pool_to_close, AsyncConnectionPool):
            logger.info("Closing database connection pool...")
            try:
                await pool_to_close.close()
            except Exception as e:
                 logger.error(f"Error closing database pool: {e}", exc_info=True)


        logger.info("Shutdown complete.")


app = FastAPI(
    title="Voice AI Assistant",
    description="Real-time voice conversation with AI (Lifespan State Mgmt).",
    version="1.2.0",
    lifespan=lifespan
)

app.include_router(api_router.router, prefix="/api", tags=["API"])

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    db_pool: AsyncConnectionPool = Depends(get_db_pool),
    groq_client: AsyncGroq = Depends(get_groq_client),
    tts_handler: TextToSpeech = Depends(get_tts_handler),
    agent: Agent = Depends(get_agent),
    deps: AgentDependencies = Depends(get_dependencies),

):
    """Handles WebSocket connections, injecting dependencies directly."""
    await handle_websocket_connection(
        websocket=websocket,
        agent=agent,
        deps=deps,
        session_id=session_id,
        db_pool=db_pool,
        groq_ai_client=groq_client,
        tts_handler=tts_handler
    )