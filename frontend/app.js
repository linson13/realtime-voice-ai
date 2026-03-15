/**
 * app.js — Main application controller
 * Wires AudioManager + VoiceWebSocket together and drives the UI.
 */

// ── DOM refs ──────────────────────────────────────────────
const btnMic       = document.getElementById('btn-mic');
const btnInterrupt = document.getElementById('btn-interrupt');
const statusBadge  = document.getElementById('status-badge');
const stateLabel   = document.getElementById('state-label');
const orb          = document.getElementById('orb');
const txYou        = document.getElementById('transcript-you');
const txAI         = document.getElementById('transcript-ai');
const ragFile      = document.getElementById('rag-file');
const ragStatus    = document.getElementById('rag-status');

// ── State ─────────────────────────────────────────────────
let appState      = 'idle';   // idle | listening | processing | speaking
let isListening   = false;
let aiTokenBuffer = '';

// ── Audio Manager ─────────────────────────────────────────
const audio = new AudioManager(
  // onAudioChunk — send raw PCM to backend
  (buffer) => {
    if (isListening) ws.sendAudio(buffer);
  }
);

// ── WebSocket ─────────────────────────────────────────────
const ws = new VoiceWebSocket(
  // onMessage (JSON control)
  handleMessage,
  // onAudio (TTS binary)
  (arrayBuffer) => audio.enqueueAudioChunk(arrayBuffer),
  // onOpen
  () => { stateLabel.textContent = 'Connected'; },
  // onClose
  () => { stateLabel.textContent = 'Reconnecting…'; }
);

ws.connect();

// ── Message Handler ───────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {

    case 'state':
      setAppState(msg.state);
      break;

    case 'transcript':
      txYou.textContent = msg.text;
      txAI.textContent  = '…';
      aiTokenBuffer     = '';
      break;

    case 'tts_sentence_end':
      // Sentence finished — nothing to do visually
      break;

    case 'interrupted':
      audio.stopPlayback();
      setAppState('listening');
      break;

    case 'rag_ready':
      ragStatus.textContent = '✅ Knowledge base loaded';
      break;

    case 'pong':
      break;

    default:
      console.log('[App] Unknown message:', msg);
  }
}

// ── State Machine ─────────────────────────────────────────
function setAppState(state) {
  appState = state;

  // Reset orb classes
  orb.className = 'orb';
  statusBadge.className = 'badge';

  switch (state) {
    case 'listening':
      orb.classList.add('pulsing');
      statusBadge.classList.add('listening');
      statusBadge.textContent = 'Listening';
      stateLabel.textContent  = 'Speak now…';
      btnInterrupt.disabled   = true;
      break;

    case 'processing':
      orb.classList.add('processing');
      statusBadge.classList.add('processing');
      statusBadge.textContent = 'Processing';
      stateLabel.textContent  = 'Thinking…';
      btnInterrupt.disabled   = false;
      break;

    case 'speaking':
      orb.classList.add('speaking');
      statusBadge.classList.add('speaking');
      statusBadge.textContent = 'Speaking';
      stateLabel.textContent  = 'AI responding…';
      btnInterrupt.disabled   = false;
      break;

    default:
      statusBadge.textContent = state;
      stateLabel.textContent  = '';
  }
}

// ── Mic Button ────────────────────────────────────────────
btnMic.addEventListener('click', async () => {
  if (!isListening) {
    try {
      await audio.startCapture();
      isListening         = true;
      btnMic.textContent  = '⏹ Stop';
      btnMic.className    = 'btn danger';
      setAppState('listening');
    } catch (e) {
      alert('Microphone access denied. Please allow mic access and try again.');
      console.error(e);
    }
  } else {
    audio.stopCapture();
    isListening         = false;
    btnMic.textContent  = '🎤 Start Listening';
    btnMic.className    = 'btn primary';
    setAppState('idle');
    statusBadge.textContent = 'Idle';
    stateLabel.textContent  = 'Ready';
    btnInterrupt.disabled   = true;
  }
});

// ── Interrupt Button ──────────────────────────────────────
btnInterrupt.addEventListener('click', () => {
  ws.sendInterrupt();
  audio.stopPlayback();
  setAppState('listening');
});

// ── RAG File Upload ───────────────────────────────────────
ragFile.addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  ragStatus.textContent = '⏳ Uploading…';
  try {
    const text = await file.text();
    ws.sendRagContent(text);
    ragStatus.textContent = '⏳ Building index…';
  } catch (err) {
    ragStatus.textContent = '❌ Upload failed';
    console.error(err);
  }
});

// ── Keepalive ping ────────────────────────────────────────
setInterval(() => {
  if (ws.connected) ws.sendControl({ type: 'ping' });
}, 25000);

// ── Initial state ─────────────────────────────────────────
setAppState('idle');
statusBadge.textContent = 'Idle';
stateLabel.textContent  = 'Click Start Listening';
