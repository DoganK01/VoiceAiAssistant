import logging
from typing import List, Optional
from datetime import datetime

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
import psycopg

from app.backend.schemas import ConversationTurn


logger = logging.getLogger(__name__)

async def check_pool_connection(pool: AsyncConnectionPool) -> bool:
     """Checks pool connectivity by getting and releasing a connection."""
     if not pool:
         return False
     try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                 await cur.execute("SELECT 1")
                 result = await cur.fetchone()
                 return result is not None and result[0] == 1
     except Exception as e:
         logger.error(f"Database pool health check failed: {e}")
         return False

async def add_conversation_turn(
    pool_or_conn: AsyncConnectionPool | psycopg.AsyncConnection,
    session_id: str,
    user_transcript: Optional[str],
    ai_response: Optional[str],
    user_timestamp: Optional[datetime],
    ai_timestamp: Optional[datetime]
) -> Optional[ConversationTurn]:
    """Adds a conversation turn with individual timestamps."""

    sql = """
        INSERT INTO conversations (
            session_id, user_transcript, ai_response, user_timestamp, ai_timestamp
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, session_id, user_transcript, ai_response,
                  user_timestamp, ai_timestamp, created_at
        """
    params = (
        session_id, user_transcript, ai_response, user_timestamp, ai_timestamp
    )

    record = None
    try:
        if isinstance(pool_or_conn, AsyncConnectionPool):
            async with pool_or_conn.connection() as conn:
                 async with conn.cursor(row_factory=dict_row) as cur:
                      await cur.execute(sql, params)
                      record = await cur.fetchone()
        elif isinstance(pool_or_conn, psycopg.AsyncConnection):
             async with pool_or_conn.cursor(row_factory=dict_row) as cur:
                  await cur.execute(sql, params)
                  record = await cur.fetchone()
        else:
             logger.error(f"Invalid type passed for pool_or_conn: {type(pool_or_conn)}")
             return None

        if record:
            logger.info(f"Conversation turn {record['id']} saved for session {session_id}")
            return ConversationTurn.model_validate(record)
        return None
    except (psycopg.Error, Exception) as e:
        logger.error(f"Failed to save conversation turn for session {session_id}: {e}", exc_info=True)
        return None

async def get_history_turns(
    pool_or_conn: AsyncConnectionPool | psycopg.AsyncConnection,
    session_id: str,
    limit: int = 20
) -> List[ConversationTurn]:
    """Retrieves history turns including individual timestamps."""
    turns = []
    sql = """
        SELECT id, session_id, user_transcript, ai_response,
               user_timestamp, ai_timestamp, created_at
        FROM conversations
        WHERE session_id = %s
        ORDER BY created_at DESC, id DESC -- Order by row creation time first
        LIMIT %s
        """
    params = (session_id, limit)
    records = []
    try:
        if isinstance(pool_or_conn, AsyncConnectionPool):
             async with pool_or_conn.connection() as conn:
                  async with conn.cursor(row_factory=dict_row) as cur:
                       await cur.execute(sql, params)
                       records = await cur.fetchall()
        elif isinstance(pool_or_conn, psycopg.AsyncConnection):
             async with pool_or_conn.cursor(row_factory=dict_row) as cur:
                  await cur.execute(sql, params)
                  records = await cur.fetchall()
        else:
             logger.error(f"Invalid type passed for pool_or_conn: {type(pool_or_conn)}")
             return []

        turns = [ConversationTurn.model_validate(record) for record in reversed(records)]
        logger.info(f"Retrieved {len(turns)} history turns for session {session_id}.")
    except (psycopg.Error, Exception) as e:
        logger.error(f"Failed to retrieve history for session {session_id}: {e}", exc_info=True)
    return turns


async def create_conversations_table(pool: AsyncConnectionPool):
    """
    Creates the 'conversations' table with individual timestamps and index
    if they don't already exist, using the provided connection pool.
    """
    if not pool or not isinstance(pool, AsyncConnectionPool):
         logger.error("Cannot create table, invalid database pool provided.")
         return

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS conversations (
        id BIGSERIAL PRIMARY KEY,
        session_id VARCHAR(255) NOT NULL,
        user_transcript TEXT,
        ai_response TEXT,
        user_timestamp TIMESTAMPTZ NULL, -- Nullable timestamp for user input
        ai_timestamp TIMESTAMPTZ NULL,   -- Nullable timestamp for AI response
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP -- Row creation time
    );
    """

    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations (session_id);
    """

    lock_acquired = False
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                logger.info("Ensuring 'conversations' table exists with new schema...")
                await cur.execute(create_table_sql)
                logger.info("Table 'conversations' ensured.")

                logger.info("Ensuring 'idx_conversations_session_id' index exists...")
                await cur.execute(create_index_sql)
                logger.info("Index 'idx_conversations_session_id' ensured.")

        logger.info("Database schema initialization check completed successfully.")

    except (psycopg.Error, Exception) as e:
        logger.error(f"Error during database schema initialization: {e}", exc_info=True)
        raise
    finally:
        if lock_acquired:
            try:
                async with pool.connection() as conn:
                     async with conn.cursor() as cur:
                         await cur.execute(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})")
                         logger.info("Released schema init advisory lock.")
            except Exception as lock_release_e:
                 logger.error(f"Failed to release schema init advisory lock: {lock_release_e}")
