import io
import logging
import numpy as np
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _load_model():
    """Load Whisper model once and cache it."""
    from faster_whisper import WhisperModel
    logger.info("Loading Whisper 'tiny' model (first run may take a moment)…")
    # cpu + int8 quantization = fastest on CPU-only machines
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    logger.info("Whisper model loaded ✓")
    return model

def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribe raw 16-bit PCM audio (16kHz mono) to text.
    Returns the transcript string.
    """
    try:
        model = _load_model()

        # Convert raw PCM bytes → float32 numpy array
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        segments, info = model.transcribe(
            samples,
            language="en",
            beam_size=1,          # Fastest beam search
            vad_filter=True,      # Built-in VAD — ignores silence
            vad_parameters=dict(
                min_silence_duration_ms=300,
                speech_pad_ms=100,
            ),
        )

        transcript = " ".join(seg.text for seg in segments).strip()
        logger.info(f"Transcribed: '{transcript}' (lang={info.language}, prob={info.language_probability:.2f})")
        return transcript

    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        return ""
