import logging
from typing import Optional, List, AsyncIterator, Tuple
from types import TracebackType
from io import BytesIO

from groq import AsyncGroq, GroqError
from openai import AsyncOpenAI, APIError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from fastapi import WebSocket

from app.backend.config.config import settings
from app.backend.agent.agent import AgentDependencies


logger = logging.getLogger(__name__)

async def speech_to_text(
    groq_client: AsyncGroq,
    audio_bytes: bytes
) -> Optional[str]:
    """
    Transcribe audio to text using the Groq client.
    Args:
        groq_client: Groq client instance.
        audio_bytes: Audio data in bytes format.
    Returns:
            Transcribed text or None if an error occurs.
    """
    logger.info(f"Sending {len(audio_bytes)} bytes to Groq STT.")
    try:
        # Use the async client directly with await
        with BytesIO(initial_bytes=audio_bytes) as audio_stream:
            audio_stream.name = "audio.wav"
            response = await groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_stream,
                language="en",
            )
        logger.info("STT successful.")
        return response.text.strip()
    except GroqError as e:
        logger.error(f"Groq STT API error: {e.status_code} - {e.body}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during STT: {e}", exc_info=True)
        return None


class TextToSpeech:
    """
    Asynchronous context manager for streaming text-to-speech conversion using OpenAI's API.

    Buffers incoming text via feed() and sends it to the API when the buffer reaches
    a certain size, a sentence-ending character is encountered, or flush() is called.
    Yields audio bytes via feed() and flush() as async iterators.

    Usage:
        tts = TextToSpeech(client=openai_client)
        async with tts:
            async for chunk in tts.feed("Hello. "): yield chunk # Might yield audio
            async for chunk in tts.feed("How are you?"): yield chunk # Might yield audio
            async for chunk in tts.flush(): yield chunk # Yields remaining audio
    """

    DEFAULT_CHUNK_SIZE = 1024 * 6

    def __init__(
        self,
        client: AsyncOpenAI,
        model_name: str = settings.OPENAI_TTS_MODEL,
        voice: str = "alloy", 
        response_format: str = "aac",
        speed: float = 1.00,
        buffer_size: int = 128,
        sentence_endings: tuple[str, ...] = ("\n"),
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """Initializes the TextToSpeech handler."""
        if not client:
             raise ValueError("AsyncOpenAI client must be provided.")

        self.client = client
        self.model_name = model_name
        self.voice = voice
        self.response_format = response_format
        self.speed = speed
        self.buffer_size = buffer_size
        self.sentence_endings = sentence_endings
        self.chunk_size = chunk_size if chunk_size > 0 else self.DEFAULT_CHUNK_SIZE
        self._buffer = "" 
        logger.debug(f"TextToSpeech initialized. Model: {model_name}, Voice: {voice}, Format: {response_format}, Text Buffer: {buffer_size}, Audio Chunk: {self.chunk_size}")

    async def __aenter__(self) -> "TextToSpeech":
        """Enters the asynchronous context, ensuring buffer is clear."""
        self._buffer = ""
        logger.debug("TextToSpeech context entered.")
        return self

    async def feed(self, text: str) -> AsyncIterator[bytes]:
        """
        Feeds text into the internal buffer. If the buffer meets flush criteria
        (size or sentence ending), it triggers synthesis of the buffered text
        and yields the resulting audio chunks.

        Args:
            text: The text chunk to add to the buffer.

        Yields:
            Audio bytes generated from flushed text, if criteria met.
        """
        if not isinstance(text, str):
             logger.warning(f"Non-string received in feed: {type(text)}. Ignoring.")
             if False: yield b'' 
             return

        self._buffer += text
        should_flush = (
            len(self._buffer) >= self.buffer_size or
            (self._buffer and self._buffer.endswith(self.sentence_endings))
        )
        if should_flush:
            logger.debug(f"Feed triggered flush (buffer size: {len(self._buffer)})")
            async for chunk in self.flush():
                yield chunk
        else:
             if False: yield b''


    async def flush(self) -> AsyncIterator[bytes]:
        """
        Forces synthesis of any remaining text in the buffer and yields audio chunks.
        Clears the buffer afterwards.

        Yields:
            Audio bytes generated from the buffered text.
        """
        text_to_send = self._buffer.strip()
        if text_to_send:
            self._buffer = ""
            logger.debug(f"Flushing text: '{text_to_send[:50]}...'")
            try:
                async for chunk in self._synthesize_text(text_to_send):
                    yield chunk
            except Exception:
                 raise
        else:
             self._buffer = ""
             logger.debug("Flush called with empty or whitespace-only buffer.")
             if False: yield b''

    async def _synthesize_text(self, text: str) -> AsyncIterator[bytes]:
        """
        Internal method: Sends text to the OpenAI TTS API using streaming
        and yields audio chunks. Handles API errors.
        Args:
            text: The text to synthesize.
        Yields:
            Audio bytes generated from the text.
        """
        logger.info(f"Sending to OpenAI TTS ({self.model_name}, {self.voice}): '{text[:50]}...'")
        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=self.model_name,
                input=text,
                voice=self.voice, # type: ignore
                response_format=self.response_format, # type: ignore
                speed=self.speed,
            ) as response:
                async for audio_chunk in response.iter_bytes(chunk_size=self.chunk_size):
                    if audio_chunk:
                        logger.debug(f"Yielding audio chunk size: {len(audio_chunk)}")
                        yield audio_chunk
            logger.info("Finished iterating TTS audio stream successfully.")

        except APIError as e:
            logger.error(f"OpenAI TTS API error: {e.status_code} - {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during TTS API call or streaming: {e}", exc_info=True)
            raise

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Exits the asynchronous context. Clears buffer.
        Note: Does NOT automatically flush remaining buffer on exit,
        rely on explicit flush() call before exiting 'async with' if needed.
        """
        logger.debug(f"Exiting TextToSpeech context. Exception type: {exc_type}")
        self._buffer = ""


async def stream_tts(
        websocket: WebSocket,
        agent: Agent,
        tts_handler: TextToSpeech,
        user_prompt: str,
        message_history: List[ModelMessage],
        deps: AgentDependencies,
) -> Tuple[str, List[ModelMessage]]:
    """
    Streams text-to-speech audio to the WebSocket connection.
    Args:
        websocket: WebSocket connection to send audio data.
        agent: PydanticAI Agent instance.
        tts_handler: TextToSpeech handler instance.
        user_prompt: User's input prompt.
        message_history: List of previous messages in the conversation stored in PostgreSQL.
        deps: Agent dependencies.
    Returns:
        The full response text generated by the agent.
    """
    full_response = ""
    async with tts_handler:
        async with agent.run_stream(
            user_prompt=user_prompt,
            message_history=message_history,
            deps=deps,
        ) as agent_result:
            async for text_chunk in agent_result.stream_text(delta=True):
                if text_chunk:
                    full_response += text_chunk
                    async for audio_chunk in tts_handler.feed(text=text_chunk):
                        await websocket.send_bytes(audio_chunk)
        async for audio_chunk in tts_handler.flush():
            await websocket.send_bytes(audio_chunk)
    return full_response, agent_result.new_messages()