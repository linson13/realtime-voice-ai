# 🎙️ Realtime Voice AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Realtime-4A90D9?style=for-the-badge&logo=websocket&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-llama3.2-black?style=for-the-badge&logo=ollama&logoColor=white)
![Whisper](https://img.shields.io/badge/Whisper-faster--whisper-412991?style=for-the-badge&logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A complete, self-hosted real-time voice conversation system built from scratch.**
**No paid APIs. No managed voice platforms. Fully local. Zero cost.**

[Features](#-features) • [Architecture](#-architecture) • [Setup](#-setup--installation) • [Usage](#-usage) • [Design Decisions](#-design-decisions) • [Latency](#-latency-considerations)

</div>

---

## ✨ Features

- 🎤 **Real-time mic streaming** via AudioWorklet (20ms chunks, not batch)
- 🧠 **Local LLM** powered by Ollama `llama3.2:3b` — no API key needed
- 🗣️ **Neural TTS** via Microsoft edge-tts — free, natural sounding voices
- 📝 **Local STT** via `faster-whisper` tiny — runs on CPU, int8 quantized
- ✋ **Interruption handling** — speak over the AI at any time
- 📚 **RAG support** — upload a `.txt` knowledge base for context-aware answers
- 🔄 **Auto-reconnect** WebSocket with exponential backoff
- 💻 **CPU-only** — no GPU required

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                        │
│                                                                   │
│  Microphone → AudioWorklet → PCM 16kHz ──────► WebSocket ───►   │
│                                                                   │
│  ◄─── Web Audio API ◄─── MP3 chunks ◄──────── WebSocket ◄───   │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   FastAPI + WebSocket  │
                    │      Gateway           │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │    Session Manager     │
                    │  (per-connection state)│
                    └───────────┬───────────┘
                                │
          ┌─────────────────────▼──────────────────────┐
          │              Voice Pipeline                  │
          │                                              │
          │  ┌──────────┐   ┌──────────┐   ┌────────┐  │
          │  │   VAD    │──►│  Whisper │──►│ Ollama │  │
          │  │(silence) │   │  (STT)   │   │ (LLM)  │  │
          │  └──────────┘   └──────────┘   └───┬────┘  │
          │                                     │        │
          │                    ┌────────────────▼──────┐ │
          │                    │  RAG (FAISS + MiniLM) │ │
          │                    └───────────────────────┘ │
          │                                     │        │
          │                              ┌──────▼──────┐ │
          │                              │  edge-tts   │ │
          │                              │   (TTS)     │ │
          │                              └─────────────┘ │
          └──────────────────────────────────────────────┘
```

### State Machine

```
                    ┌─────────────┐
           ┌───────►│  LISTENING  │◄──────────────┐
           │        └──────┬──────┘               │
           │               │ speech detected       │
           │        ┌──────▼──────┐               │
           │        │ PROCESSING  │               │
           │        │ (STT + LLM) │               │
           │        └──────┬──────┘               │
           │               │ response ready        │
           │        ┌──────▼──────┐               │
           └────────│  SPEAKING   │───────────────┘
          interrupt │  (TTS out)  │  done speaking
                    └─────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Vanilla JS + AudioWorklet | Low-latency mic capture |
| **Transport** | WebSocket (binary + JSON) | Bidirectional streaming |
| **Backend** | FastAPI + asyncio | Async gateway |
| **STT** | `faster-whisper` tiny (int8) | Speech-to-text, CPU optimized |
| **LLM** | Ollama `llama3.2:3b` | Local language model |
| **TTS** | `edge-tts` (Microsoft Neural) | Free neural voice synthesis |
| **RAG** | FAISS + `all-MiniLM-L6-v2` | Local vector search |
| **VAD** | Energy-based (numpy) | Silence detection |

---

## 📋 Prerequisites

| Requirement | Version | Link |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org/downloads/release/python-3119/) |
| Ollama | Latest | [ollama.com](https://ollama.com) |
| Git | Any | [git-scm.com](https://git-scm.com) |

> ⚠️ **Python 3.14 is NOT supported** — use Python 3.11 for best compatibility with ML libraries.

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/linson13/realtime-voice-ai.git
cd realtime-voice-ai
```

### 2. Install Ollama and pull the model

Download Ollama from [ollama.com](https://ollama.com), then:

```bash
ollama pull llama3.2:3b
```

> This is a one-time ~2GB download. Ollama runs automatically in the background on Windows.

### 3. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Start the server

```bash
py -3.11 main.py
```

### 5. Open in browser

```
http://localhost:8000
```

---

## 💡 Usage

1. Click **🎤 Start Listening**
2. Allow microphone access when prompted
3. **Speak naturally** — the system auto-detects when you stop
4. Wait for the AI to respond (~7-10s on CPU-only)
5. Click **✋ Interrupt** anytime to stop the AI mid-response

### Optional: RAG Knowledge Base

1. Prepare a `.txt` file with your knowledge content
2. Click **📄 Upload Knowledge Base**
3. Wait for *"✅ Knowledge base loaded"*
4. The AI now answers using your documents as context

---

## ⚡ Latency Considerations

| Stage | Strategy | CPU-only Time |
|---|---|---|
| End-of-speech detection | Energy VAD + 1.5s silence window | ~1.5s |
| Speech → Transcript | Whisper tiny, int8, VAD filter | ~1-2s |
| Transcript → LLM first token | llama3.2:3b streaming | ~4-6s |
| LLM → Audio starts | Sentence-level TTS streaming | ~0.5-1s |
| **Total E2E** | | **~7-10s** |

### Key Latency Optimisations

- **AudioWorklet** over MediaRecorder — 20ms chunks vs 500ms batches
- **Sentence-level TTS streaming** — audio starts before full LLM response
- **int8 quantization** on Whisper — 2x faster on CPU
- **Streaming LLM** (`stream=True`) — first token arrives immediately
- **edge-tts offloads TTS** to Microsoft servers — saves local CPU entirely

---

## 🔧 Design Decisions

### Why AudioWorklet over MediaRecorder?
MediaRecorder buffers audio in 500ms+ chunks. AudioWorklet gives true 20ms streaming, enabling real-time VAD and much faster interruption response.

### Why edge-tts over local Piper TTS?
On a CPU-only system, running Whisper + Ollama already saturates resources. edge-tts offloads synthesis to Microsoft's free servers, saving CPU for STT and LLM.

### Why sentence-level TTS streaming?
Waiting for the full LLM response before speaking adds 5-10 seconds. By piping tokens sentence-by-sentence into TTS, the user hears the first sentence ~1s after the LLM starts generating.

### Why asyncio.Task cancellation for interrupts?
Python's asyncio allows clean task cancellation with `task.cancel()`. This immediately stops the LLM stream and TTS pipeline without leaving dangling threads.

---

## ⚖️ Known Trade-offs

| Trade-off | Reason | Mitigation |
|---|---|---|
| ~7-10s latency | CPU-only inference | Use GPU for <2s latency |
| Whisper tiny accuracy | Speed over accuracy | Upgrade to `base` model if RAM allows |
| 1.5s silence window | Avoid cutting mid-sentence | Tunable via `_SILENCE_LIMIT` in `pipeline.py` |
| edge-tts needs internet | Microsoft server | Swap for `piper-tts` for fully offline |
| No speaker diarization | Single-user focus | Sufficient for 1:1 voice assistant |

---

## 📁 Project Structure

```
realtime-voice-ai/
│
├── backend/
│   ├── main.py           # FastAPI app + WebSocket gateway
│   ├── pipeline.py       # Core voice pipeline + state machine
│   ├── session.py        # Session registry
│   ├── stt.py            # Whisper STT (faster-whisper)
│   ├── llm.py            # Ollama streaming LLM client
│   ├── tts.py            # edge-tts streaming synthesis
│   ├── rag.py            # FAISS + sentence-transformers RAG
│   └── requirements.txt  # Python dependencies
│
└── frontend/
    ├── index.html        # UI shell
    ├── style.css         # Dark theme styles
    ├── ws.js             # WebSocket client + auto-reconnect
    ├── audio.js          # AudioWorklet capture + Web Audio playback
    └── app.js            # App controller + state machine
```

---

## 🔮 Upgrading for Production

| Component | Current | Production Upgrade |
|---|---|---|
| STT | Whisper tiny | Whisper `small` or `medium` |
| LLM | llama3.2:3b local | llama3.1:8b or hosted API |
| TTS | edge-tts | ElevenLabs / Piper TTS |
| Transport | WebSocket | WebRTC (lower latency) |
| Sessions | In-memory | Redis |
| Deployment | Local | Docker + HTTPS/WSS |

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<div align="center">

Built with ❤️ using FastAPI, Whisper, Ollama, and edge-tts

**No paid APIs. No managed platforms. Just clean systems engineering.**

</div>
