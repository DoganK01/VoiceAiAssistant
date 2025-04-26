from typing import List, Optional, Any, Tuple
import logging
import datetime
from datetime import datetime

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.backend.schemas import ConversationTurn
from app.backend.config.config import settings

logger = logging.getLogger(__name__)

def format_messages_for_agent(
    conversation_history: List[ConversationTurn],
) -> List[ModelMessage]:
    """
    Formats the conversation history retrieved from the database
    (as ConversationTurn objects) into the list of ModelMessage objects
    required by a PydanticAI agent.

    Args:
        conversation_history: List of ConversationTurn Pydantic models.

    Returns:
        List of ModelMessage objects (ModelRequest or ModelResponse).
    """
    messages: List[ModelMessage] = []
    logger.debug(f"Formatting {len(conversation_history)} turns for agent.")

    for turn in conversation_history:
        if turn.user_transcript:
            try:
                ts_user = turn.user_timestamp or datetime.now(datetime.timezone.utc)
                messages.append(
                    ModelRequest(
                        parts=[
                            UserPromptPart(
                                content=turn.user_transcript, 
                                timestamp=ts_user, 
                                part_kind='user-prompt'
                                ),
                            ],
                            kind='request',
                        ),
                )
            except Exception as e:
                 logger.error(f"Error creating ModelRequest for user transcript: {e}", exc_info=True)

        if turn.ai_response:
            try:
                ts_ai = turn.ai_timestamp or datetime.now(datetime.timezone.utc)
                messages.append(
                    ModelResponse(
                        parts=[
                            TextPart(
                                content=turn.ai_response, 
                                part_kind='text'
                                )
                            ],
                            model_name='gpt-4o',
                            timestamp=ts_ai,
                            kind='response',
                        ),
                )
            except Exception as e:
                logger.error(f"Error creating ModelResponse for AI response: {e}", exc_info=True)

        else:
            continue

    logger.debug(f"Formatted history into {len(messages)} agent messages.")
    return messages


def parse_agent_result(
    processed_result: Any
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses the result from the agent/TTS stream (expected to be a list of ModelMessage,
    potentially including tool calls/returns) to extract the final AI text response
    and the relevant user/AI timestamps for database storage.

    Args:
        processed_result: The result returned by the stream_tts function
                          (expected: List[ModelMessage]).

    Returns:
        A tuple containing:
        - last_user_prompt_timestamp (Optional[datetime])
        - final_ai_response_timestamp (Optional[datetime])
    """
    last_user_prompt_timestamp: Optional[datetime] = None
    final_ai_response_timestamp: Optional[datetime] = None

    if isinstance(processed_result, list) and processed_result:
        logger.debug(f"Parsing agent result list with {len(processed_result)} messages.")

        temp_user_ts = None
        for msg in processed_result:
             if isinstance(msg, ModelRequest) and hasattr(msg, 'parts') and msg.parts:
                  for part in msg.parts:
                       if isinstance(part, UserPromptPart):
                            part_ts = getattr(part, 'timestamp', None)
                            if part_ts:
                                 temp_user_ts = part_ts
        last_user_prompt_timestamp = temp_user_ts
        if last_user_prompt_timestamp:
             logger.debug(f"Found last user timestamp: {last_user_prompt_timestamp}")
        else:
             logger.warning("Could not find any UserPromptPart timestamp in agent result.")

        for msg in reversed(processed_result):
             if isinstance(msg, ModelResponse) and hasattr(msg, 'parts') and msg.parts:
                  text_content_parts = [
                      getattr(part, 'content', '')
                      for part in msg.parts
                      if isinstance(part, TextPart) and getattr(part, 'content', None)
                  ]
                  if text_content_parts:
                       final_ai_response_timestamp = getattr(msg, 'timestamp', None)
                       logger.debug(f"Found final AI response timestamp: {final_ai_response_timestamp}")
                       break

        if final_ai_response_timestamp is None:
            logger.warning("Could not find timestamp in the final text ModelResponse.")

    else:
         logger.error(f"stream_tts did not return the expected agent message list. Type: {type(processed_result)}")

    return last_user_prompt_timestamp, final_ai_response_timestamp