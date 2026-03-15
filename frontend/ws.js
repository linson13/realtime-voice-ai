/**
 * ws.js — WebSocket client
 * Handles connection, reconnection, sending audio + control messages.
 */

class VoiceWebSocket {
  constructor(onMessage, onAudio, onOpen, onClose) {
    this.onMessage = onMessage;
    this.onAudio   = onAudio;
    this.onOpen    = onOpen;
    this.onClose   = onClose;

    this.ws         = null;
    this.sessionId  = crypto.randomUUID();
    this._reconnectDelay = 1000;
    this._maxDelay       = 10000;
  }

  connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${location.host}/ws/${this.sessionId}`;
    console.log("[WS] Connecting to", url);

    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      console.log("[WS] Connected");
      this._reconnectDelay = 1000;
      this.onOpen?.();
    };

    this.ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary = audio chunk from TTS
        this.onAudio?.(event.data);
      } else {
        // Text = JSON control message
        try {
          const msg = JSON.parse(event.data);
          this.onMessage?.(msg);
        } catch (e) {
          console.warn("[WS] Non-JSON message:", event.data);
        }
      }
    };

    this.ws.onclose = (e) => {
      console.log("[WS] Closed:", e.code, e.reason);
      this.onClose?.();
      // Auto-reconnect
      setTimeout(() => this.connect(), this._reconnectDelay);
      this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxDelay);
    };

    this.ws.onerror = (e) => {
      console.error("[WS] Error:", e);
    };
  }

  /** Send raw PCM audio bytes */
  sendAudio(buffer) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(buffer);
    }
  }

  /** Send a JSON control message */
  sendControl(obj) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  sendInterrupt() {
    this.sendControl({ type: "interrupt" });
  }

  sendRagContent(text) {
    this.sendControl({ type: "rag_upload", content: text });
  }

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
