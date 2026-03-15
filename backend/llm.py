import json
import logging
import httpx
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"

SYSTEM_PROMPT = """You are a helpful, concise voice assistant. 
Respond naturally as if speaking out loud.
Keep responses SHORT (2-4 sentences max) unless the user asks for detail.
Do NOT use markdown, bullet points, or special formatting.
Speak in plain conversational English."""

async def stream_llm_response(
    user_text: str,
    history: list[dict],
    rag_context: str = "",
) -> AsyncGenerator[str, None]:
    """
    Stream token-by-token LLM response from Ollama.
    Yields text tokens as they arrive.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject RAG context if available
    if rag_context:
        messages.append({
            "role": "system",
            "content": f"Use this knowledge base to help answer:\n\n{rag_context}"
        })

    # Add conversation history
    messages.extend(history[-10:])  # Last 5 turns

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   True,
        "options": {
            "temperature": 0.7,
            "num_predict": 200,   # Max tokens — keep responses short for voice
            "num_ctx":     2048,  # Context window — small for speed
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Is it running? Run: ollama serve")
        yield "Sorry, I'm having trouble connecting to my brain right now. Please make sure Ollama is running."
    except Exception as e:
        logger.error(f"LLM error: {e}", exc_info=True)
        yield "Sorry, I encountered an error. Please try again."
