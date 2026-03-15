import asyncio
import json
import logging
import io
import time
import numpy as np
from enum import Enum
from stt import transcribe_audio
from llm import stream_llm_response
from tts import synthesize_speech
from rag import RAGEngine

logger = logging.getLogger(__name__)

class State(Enum):
    LISTENING   = "listening"
    PROCESSING  = "processing"
    SPEAKING    = "speaking"

class VoicePipeline:
    def __init__(self, session_id: str, websocket):
        self.session_id = session_id
        self.websocket  = websocket
        self.state      = State.LISTENING

        # Audio buffer — accumulates mic chunks
        self._audio_buffer   = bytearray()
        self._silence_frames = 0
        self._SILENCE_LIMIT  = 30   # ~1.5s of silence at 20ms chunks → trigger STT
        self._MIN_AUDIO_MS   = 300  # ignore clips shorter than 300ms

        # Cancellation token for ongoing LLM/TTS tasks
        self._current_task: asyncio.Task | None = None

        # Conversation history for multi-turn context
        self._history = []

        # RAG engine (optional)
        self._rag = RAGEngine()

        logger.info(f"[{self.session_id}] Pipeline initialised")

    # ------------------------------------------------------------------ #
    #  AUDIO INPUT                                                         #
    # ------------------------------------------------------------------ #
    async def handle_audio_chunk(self, chunk: bytes):
        """
        Called for every audio chunk streamed from the browser.
        We accumulate bytes and detect end-of-speech via silence.
        """
        if self.state == State.SPEAKING:
            # User started speaking while AI is responding → interrupt
            await self.handle_interrupt()

        if self.state != State.LISTENING:
            return

        # Simple energy-based VAD on raw PCM
        is_silent = self._is_silent(chunk)

        if is_silent:
            self._silence_frames += 1
        else:
            self._silence_frames = 0
            self._audio_buffer.extend(chunk)

        # Flush: user paused long enough after speaking
        if self._silence_frames >= self._SILENCE_LIMIT and len(self._audio_buffer) > 0:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer.clear()
            self._silence_frames = 0

            duration_ms = (len(audio_data) / 2 / 16000) * 1000  # 16-bit mono 16kHz
            if duration_ms < self._MIN_AUDIO_MS:
                logger.debug(f"[{self.session_id}] Audio too short ({duration_ms:.0f}ms), skipping")
                return

            logger.info(f"[{self.session_id}] Speech detected ({duration_ms:.0f}ms), processing…")
            self._current_task = asyncio.create_task(self._run_pipeline(audio_data))

    def _is_silent(self, chunk: bytes, threshold: int = 300) -> bool:
        """Energy-based silence detection on 16-bit PCM."""
        try:
            samples = np.frombuffer(chunk, dtype=np.int16)
            rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
            return rms < threshold
        except Exception:
            return True

    # ------------------------------------------------------------------ #
    #  MAIN PIPELINE                                                       #
    # ------------------------------------------------------------------ #
    async def _run_pipeline(self, audio_data: bytes):
        t0 = time.time()
        try:
            # ── 1. STATE: PROCESSING ────────────────────────────────────
            self.state = State.PROCESSING
            await self._send_state("processing")

            # ── 2. STT ─────────────────────────────────────────────────
            logger.info(f"[{self.session_id}] STT start")
            transcript = await asyncio.to_thread(transcribe_audio, audio_data)
            logger.info(f"[{self.session_id}] STT done: '{transcript}' ({time.time()-t0:.2f}s)")

            if not transcript or transcript.strip() == "":
                await self._send_state("listening")
                self.state = State.LISTENING
                return

            await self._send_json({"type": "transcript", "text": transcript})

            # ── 3. RAG context (if knowledge base loaded) ───────────────
            rag_context = ""
            if self._rag.is_ready():
                rag_context = self._rag.query(transcript)
                logger.info(f"[{self.session_id}] RAG context retrieved")

            # ── 4. LLM ─────────────────────────────────────────────────
            logger.info(f"[{self.session_id}] LLM start")
            self.state = State.SPEAKING
            await self._send_state("speaking")

            full_response = ""
            sentence_buffer = ""

            async for token in stream_llm_response(transcript, self._history, rag_context):
                if self.state != State.SPEAKING:
                    logger.info(f"[{self.session_id}] LLM stream cancelled (interrupt)")
                    break

                full_response  += token
                sentence_buffer += token

                # Stream TTS sentence-by-sentence for low latency
                if any(sentence_buffer.endswith(p) for p in [".", "?", "!", "\n"]):
                    sentence = sentence_buffer.strip()
                    sentence_buffer = ""
                    if sentence:
                        await self._speak(sentence)

            # Flush any remaining text
            if sentence_buffer.strip() and self.state == State.SPEAKING:
                await self._speak(sentence_buffer.strip())

            # ── 5. Update history ───────────────────────────────────────
            if full_response:
                self._history.append({"role": "user",      "content": transcript})
                self._history.append({"role": "assistant",  "content": full_response})
                # Keep last 10 turns to avoid context overflow
                self._history = self._history[-20:]

            logger.info(f"[{self.session_id}] Pipeline complete ({time.time()-t0:.2f}s)")

        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Pipeline task cancelled")
        except Exception as e:
            logger.error(f"[{self.session_id}] Pipeline error: {e}", exc_info=True)
        finally:
            if self.state != State.LISTENING:
                self.state = State.LISTENING
                await self._send_state("listening")

    # ------------------------------------------------------------------ #
    #  TTS STREAMING                                                       #
    # ------------------------------------------------------------------ #
    async def _speak(self, text: str):
        """Convert text → audio and stream chunks to frontend."""
        if self.state != State.SPEAKING:
            return
        try:
            logger.info(f"[{self.session_id}] TTS: '{text[:60]}…'")
            async for audio_chunk in synthesize_speech(text):
                if self.state != State.SPEAKING:
                    break
                await self.websocket.send_bytes(audio_chunk)
            # Signal end of this sentence
            await self._send_json({"type": "tts_sentence_end"})
        except Exception as e:
            logger.error(f"[{self.session_id}] TTS error: {e}")

    # ------------------------------------------------------------------ #
    #  INTERRUPTION                                                        #
    # ------------------------------------------------------------------ #
    async def handle_interrupt(self):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self.state = State.LISTENING
        await self._send_json({"type": "interrupted"})
        await self._send_state("listening")
        logger.info(f"[{self.session_id}] Interrupted, back to listening")

    # ------------------------------------------------------------------ #
    #  RAG                                                                 #
    # ------------------------------------------------------------------ #
    async def load_rag_content(self, text: str):
        await asyncio.to_thread(self._rag.load, text)
        logger.info(f"[{self.session_id}] RAG knowledge base loaded")

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    async def _send_json(self, data: dict):
        try:
            await self.websocket.send_text(json.dumps(data))
        except Exception:
            pass

    async def _send_state(self, state: str):
        await self._send_json({"type": "state", "state": state})

    async def cleanup(self):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        logger.info(f"[{self.session_id}] Pipeline cleaned up")
