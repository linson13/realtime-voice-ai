/**
 * audio.js — Mic capture + TTS playback
 *
 * Capture: AudioWorklet → raw PCM (16-bit, 16kHz, mono) → WebSocket
 * Playback: MP3 chunks → MediaSource / AudioContext queue
 */

class AudioManager {
  constructor(onAudioChunk, onSilence, onSpeech) {
    this.onAudioChunk = onAudioChunk; // callback(Int16Array)
    this.onSilence    = onSilence;
    this.onSpeech     = onSpeech;

    this._audioCtx      = null;
    this._mediaStream   = null;
    this._workletNode   = null;
    this._isCapturing   = false;

    // Playback queue
    this._playbackCtx    = null;
    this._audioQueue     = [];
    this._isPlaying      = false;
    this._sourceNode     = null;
    this._mediaSource    = null;
    this._sourceBuffer   = null;
    this._pendingChunks  = [];
  }

  // ──────────────────────────────────────────────
  //  MIC CAPTURE
  // ──────────────────────────────────────────────
  async startCapture() {
    if (this._isCapturing) return;

    this._mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
    });

    this._audioCtx = new AudioContext({ sampleRate: 16000 });

    // Load inline AudioWorklet processor
    const workletBlob = new Blob([`
      class PCMProcessor extends AudioWorkletProcessor {
        constructor() {
          super();
          this._buffer = [];
          this._CHUNK_SIZE = 320; // 20ms at 16kHz
        }
        process(inputs) {
          const input = inputs[0]?.[0];
          if (!input) return true;
          for (let i = 0; i < input.length; i++) {
            this._buffer.push(Math.max(-1, Math.min(1, input[i])));
          }
          while (this._buffer.length >= this._CHUNK_SIZE) {
            const chunk = this._buffer.splice(0, this._CHUNK_SIZE);
            // Convert float32 → int16
            const pcm = new Int16Array(this._CHUNK_SIZE);
            for (let i = 0; i < this._CHUNK_SIZE; i++) {
              pcm[i] = Math.round(chunk[i] * 32767);
            }
            this.port.postMessage(pcm.buffer, [pcm.buffer]);
          }
          return true;
        }
      }
      registerProcessor('pcm-processor', PCMProcessor);
    `], { type: 'application/javascript' });

    const workletUrl = URL.createObjectURL(workletBlob);
    await this._audioCtx.audioWorklet.addModule(workletUrl);
    URL.revokeObjectURL(workletUrl);

    const source = this._audioCtx.createMediaStreamSource(this._mediaStream);
    this._workletNode = new AudioWorkletNode(this._audioCtx, 'pcm-processor');

    this._workletNode.port.onmessage = (e) => {
      this.onAudioChunk?.(e.data); // ArrayBuffer of Int16
    };

    source.connect(this._workletNode);
    this._isCapturing = true;
    console.log("[Audio] Capture started ✓");
  }

  stopCapture() {
    this._mediaStream?.getTracks().forEach(t => t.stop());
    this._workletNode?.disconnect();
    this._audioCtx?.close();
    this._isCapturing = false;
    console.log("[Audio] Capture stopped");
  }

  // ──────────────────────────────────────────────
  //  PLAYBACK (MP3 stream from TTS)
  // ──────────────────────────────────────────────
  initPlayback() {
    this._playbackCtx = new AudioContext();
  }

  async enqueueAudioChunk(arrayBuffer) {
    if (!this._playbackCtx) this.initPlayback();
    this._pendingChunks.push(arrayBuffer);
    if (!this._isPlaying) {
      this._isPlaying = true;
      this._drainQueue();
    }
  }

  async _drainQueue() {
    while (this._pendingChunks.length > 0) {
      const chunks = [...this._pendingChunks];
      this._pendingChunks = [];

      // Concatenate all pending chunks
      const totalLength = chunks.reduce((s, c) => s + c.byteLength, 0);
      const merged = new Uint8Array(totalLength);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(new Uint8Array(chunk), offset);
        offset += chunk.byteLength;
      }

      try {
        const audioBuffer = await this._playbackCtx.decodeAudioData(merged.buffer);
        await this._playBuffer(audioBuffer);
      } catch (e) {
        // Some chunks are incomplete — buffer more
        this._pendingChunks.unshift(...chunks);
        await new Promise(r => setTimeout(r, 50));
        break;
      }
    }
    this._isPlaying = this._pendingChunks.length > 0;
    if (this._isPlaying) this._drainQueue();
  }

  _playBuffer(audioBuffer) {
    return new Promise((resolve) => {
      const source = this._playbackCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this._playbackCtx.destination);
      source.onended = resolve;
      source.start();
      this._sourceNode = source;
    });
  }

  stopPlayback() {
    this._pendingChunks = [];
    this._isPlaying     = false;
    try { this._sourceNode?.stop(); } catch {}
    this._sourceNode = null;
  }

  get isCapturing() { return this._isCapturing; }
}
