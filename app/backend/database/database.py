import logging
from typing import List, Optional
from datetime import datetime

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
import psycopg

from app.backend.schemas import ConversationTurn

ADVISORY_LOCK_ID = 9876543210

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
    # Accept individual fields including timestamps
    session_id: str,
    user_transcript: Optional[str],
    ai_response: Optional[str],
    user_timestamp: Optional[datetime],
    ai_timestamp: Optional[datetime]
) -> Optional[ConversationTurn]:
    """Adds a conversation turn with individual timestamps."""
    # SQL includes new timestamp columns
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
        # Logic to use pool or connection remains the same
        if isinstance(pool_or_conn, AsyncConnectionPool):
            async with pool_or_conn.connection() as conn:
                 async with conn.cursor(row_factory=dict_row) as cur:
                      await cur.execute(sql, params)
                      record = await cur.fetchone()
        elif isinstance(pool_or_conn, psycopg.AsyncConnection):
             # Assume connection is already managed (e.g., within caller's 'async with')
             async with pool_or_conn.cursor(row_factory=dict_row) as cur:
                  await cur.execute(sql, params)
                  record = await cur.fetchone()
        else:
             logger.error(f"Invalid type passed for pool_or_conn: {type(pool_or_conn)}")
             return None

        if record:
            logger.info(f"Conversation turn {record['id']} saved for session {session_id}")
            # Validate and return Pydantic model
            return ConversationTurn.model_validate(record)
        return None
    except (psycopg.Error, Exception) as e: # Catch specific DB errors if possible
        logger.error(f"Failed to save conversation turn for session {session_id}: {e}", exc_info=True)
        # Consider specific error handling (e.g., DataError, IntegrityError)
        return None

async def get_history_turns(
    pool_or_conn: AsyncConnectionPool | psycopg.AsyncConnection,
    session_id: str,
    limit: int = 20 # Limit the number of *rows* (turns) fetched
) -> List[ConversationTurn]:
    """Retrieves history turns including individual timestamps."""
    turns = []
    # SQL selects new timestamp columns
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
        # Logic to use pool or connection remains the same
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

        # Convert records to Pydantic models and reverse to get chronological order
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
    # Check if pool is open might be needed depending on when this is called
    # if not pool.is_open():
    #      logger.error("Cannot create table, database pool is not open.")
    #      return

    # Use BIGSERIAL for auto-incrementing bigint primary key
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

    lock_acquired = False # Flag for advisory lock (optional)
    try:
        async with pool.connection() as conn:
            # --- Optional: Acquire Advisory Lock ---
            # Uncomment if running multiple backend instances concurrently during startup
            # logger.debug(f"Attempting to acquire advisory lock {ADVISORY_LOCK_ID}...")
            # async with conn.cursor() as cur:
            #     await cur.execute(f"SELECT pg_try_advisory_lock({ADVISORY_LOCK_ID})")
            #     lock_acquired = await cur.fetchone()[0]
            #     if not lock_acquired:
            #         logger.warning("Could not acquire schema init advisory lock, another instance might be initializing.")
            #         return # Exit if lock not acquired
            # logger.info("Acquired schema init advisory lock.")
            # --- End Optional Advisory Lock ---

            # Proceed with table/index creation
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
        # Consider re-raising if table creation is critical for startup
        raise # Re-raise error to potentially stop app startup
    finally: # --- Optional: Release Advisory Lock ---
        if lock_acquired:
            try:
                # Use the same pool to get a connection to release the lock
                async with pool.connection() as conn:
                     async with conn.cursor() as cur:
                         await cur.execute(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})")
                         logger.info("Released schema init advisory lock.")
            except Exception as lock_release_e:
                 logger.error(f"Failed to release schema init advisory lock: {lock_release_e}")
        # --- End Optional Advisory Lock ---