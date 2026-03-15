import asyncio
import json
import logging
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from session import SessionManager
from pipeline import VoicePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Real-Time Voice AI")
session_manager = SessionManager()

# Serve frontend
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")

    pipeline = VoicePipeline(session_id, websocket)
    session_manager.register(session_id, pipeline)

    try:
        while True:
            message = await websocket.receive()

            # Audio bytes from mic
            if "bytes" in message:
                await pipeline.handle_audio_chunk(message["bytes"])

            # Control messages (interrupt, etc.)
            elif "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "interrupt":
                    logger.info(f"[{session_id}] Interrupt received")
                    await pipeline.handle_interrupt()

                elif msg_type == "rag_upload":
                    text = data.get("content", "")
                    await pipeline.load_rag_content(text)
                    await websocket.send_text(json.dumps({"type": "rag_ready"}))

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
    except Exception as e:
        logger.error(f"[{session_id}] Error: {e}")
    finally:
        await pipeline.cleanup()
        session_manager.unregister(session_id)

@app.get("/health")
async def health():
    return {"status": "ok", "sessions": session_manager.count()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
