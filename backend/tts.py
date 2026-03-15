import io
import logging
import asyncio
import edge_tts
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Free Microsoft Edge voices — no API key needed
VOICE = "en-US-AriaNeural"   # Natural sounding female voice
# Other good options:
# "en-US-GuyNeural"          — Male voice
# "en-GB-SoniaNeural"        — British female
# "en-IN-NeerjaNeural"       — Indian English female

async def synthesize_speech(text: str) -> AsyncGenerator[bytes, None]:
    """
    Convert text → MP3 audio chunks using edge-tts.
    Streams audio chunks as they are generated.
    Microsoft's free TTS — no API key, no cost.
    """
    if not text or not text.strip():
        return

    try:
        communicate = edge_tts.Communicate(text=text, voice=VOICE, rate="+5%")

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    except Exception as e:
        logger.error(f"TTS error for text '{text[:50]}': {e}", exc_info=True)
        # Yield empty bytes so pipeline doesn't crash
        return
