# 🎙️ Real-Time Voice AI System

A complete, self-hosted real-time voice conversation system built from scratch.
**No paid APIs. No managed voice platforms. Fully local.**

---

## Architecture

```
Browser (Frontend)
│
│  Mic → AudioWorklet (PCM 16kHz) ──── WebSocket ────► Backend
│                                                         │
│                                                    ┌────▼─────┐
│                                                    │ Session  │
│                                                    │ Manager  │
│                                                    └────┬─────┘
│                                                         │
│                                                    ┌────▼──────────────────┐
│                                                    │  Voice Pipeline       │
│                                                    │                       │
│                                                    │  1. VAD (silence det) │
│                                                    │  2. STT  (Whisper)    │
│                                                    │  3. RAG  (optional)   │
│                                                    │  4. LLM  (Ollama)     │
│                                                    │  5. TTS  (edge-tts)   │
│                                                    └────┬──────────────────┘
│                                                         │
│  Speaker ◄── Web Audio API ◄────── WebSocket ◄──── MP3 chunks
```

### Components

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | Vanilla JS + AudioWorklet | No framework overhead, low latency |
| **WebSocket Gateway** | FastAPI + `websockets` | Async, handles binary + JSON |
| **STT** | `faster-whisper` (tiny model) | Local, fast, no API key |
| **LLM** | Ollama `llama3.2:3b` | Free, runs on CPU, good quality |
| **TTS** | `edge-tts` (Microsoft Neural) | Free, cloud-processed (saves CPU) |
| **RAG** | FAISS + `sentence-transformers` | Fully local vector search |

---

## Design Decisions

### 1. AudioWorklet over MediaRecorder
MediaRecorder batches audio (500ms+). AudioWorklet gives us 20ms chunks, enabling true streaming STT and faster interruption detection.

### 2. Raw PCM → Int16 transport
Sending raw PCM (not compressed audio) over WebSocket avoids decode overhead on the backend. Whisper accepts float32/int16 numpy arrays directly.

### 3. Sentence-level TTS streaming
Instead of waiting for the full LLM response, we pipe LLM tokens into TTS sentence-by-sentence. The user hears the first sentence ~1s before the full response is ready.

### 4. Edge-TTS for TTS
Microsoft's neural voices are processed on their servers (free, no key). This offloads TTS compute entirely from the local machine — critical for CPU-only systems.

### 5. State machine for turn-taking
```
LISTENING → (speech detected) → PROCESSING → (LLM+TTS) → SPEAKING → LISTENING
               ↑                                              │
               └──────────── (interrupt signal) ─────────────┘
```

### 6. Interruption handling
- Browser detects user speech during AI playback → sends `interrupt` JSON message
- Backend cancels the asyncio Task running LLM+TTS pipeline
- Audio buffer is flushed on frontend
- State resets to LISTENING immediately

---

## Latency Considerations

| Stage | Strategy | Expected time (CPU-only) |
|---|---|---|
| Speech end detection | Energy-based VAD + 1.5s silence window | ~1.5s |
| STT (Whisper tiny) | int8 quantized, VAD filter | ~1-2s |
| LLM first token | llama3.2:3b on CPU | ~4-6s |
| TTS first audio | Sentence streaming via edge-tts | ~0.5-1s |
| **Total E2E** | | **~7-10s** |

**Note:** With a GPU, total E2E drops to ~1-2s.

---

## Known Trade-offs

| Trade-off | Reason | Mitigation |
|---|---|---|
| ~7-10s latency | CPU-only inference | Acceptable for demo; use GPU for prod |
| Whisper tiny accuracy | Smallest model for speed | Upgrade to `base` or `small` if RAM allows |
| 1.5s silence window | Avoid cutting off mid-sentence | Tunable via `_SILENCE_LIMIT` in pipeline.py |
| edge-tts requires internet | Microsoft server | Swap for `piper-tts` for fully offline TTS |
| No speaker diarization | Single-user session | Sufficient for 1:1 voice assistant |

---

## Prerequisites

1. **Python 3.11+** — https://python.org
2. **Ollama** — https://ollama.com (Windows installer available)
3. **Node.js** — Not required (pure Python backend + vanilla JS)

---

## Setup & Run

### Step 1 — Install Ollama and pull model
```bash
# After installing Ollama from https://ollama.com
ollama pull llama3.2:3b
```

### Step 2 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Start Ollama server (in a separate terminal)
```bash
ollama serve
```

### Step 4 — Start the backend
```bash
cd backend
python main.py
```

### Step 5 — Open the frontend
Open your browser and go to:
```
http://localhost:8000
```

---

## Using the System

1. Click **"🎤 Start Listening"**
2. Allow microphone access when prompted
3. Speak naturally — the system detects when you stop speaking
4. Wait ~7-10 seconds for the AI to respond (CPU-only)
5. Click **"✋ Interrupt"** at any time to stop the AI and speak again

### Optional: Upload a Knowledge Base (RAG)
1. Prepare a `.txt` file with your knowledge base content
2. Click **"📄 Upload Knowledge Base"** and select your file
3. Wait for "✅ Knowledge base loaded"
4. The AI will now answer based on your documents

---

## Project Structure

```
voiceai/
├── backend/
│   ├── main.py          # FastAPI app + WebSocket gateway
│   ├── pipeline.py      # STT → LLM → TTS orchestration + state machine
│   ├── session.py       # Session registry
│   ├── stt.py           # Whisper transcription (faster-whisper)
│   ├── llm.py           # Ollama streaming LLM client
│   ├── tts.py           # edge-tts streaming TTS
│   ├── rag.py           # FAISS + sentence-transformers RAG
│   └── requirements.txt
└── frontend/
    ├── index.html       # UI shell
    ├── style.css        # Styles
    ├── ws.js            # WebSocket client
    ├── audio.js         # AudioWorklet capture + Web Audio playback
    └── app.js           # App controller + state machine
```

---

## Bonus: RAG Architecture

```
Upload .txt
     │
     ▼
Chunk text (300 words/chunk)
     │
     ▼
Embed with all-MiniLM-L6-v2 (384d vectors)
     │
     ▼
Store in FAISS IndexFlatIP
     │
On query:
     │
     ▼
Embed user question
     │
     ▼
Top-3 nearest chunks (cosine similarity)
     │
     ▼
Inject into LLM system prompt
```

---

## Upgrading for Production

- Replace `faster-whisper tiny` → `base` or `small` for better accuracy
- Replace `llama3.2:3b` → `llama3.1:8b` or hosted LLM API for better quality
- Replace `edge-tts` → `piper-tts` for fully offline operation
- Add Redis for multi-instance session management
- Add HTTPS/WSS for deployment
- Add WebRTC for lower latency transport
