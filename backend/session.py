import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self._sessions = {}

    def register(self, session_id: str, pipeline):
        self._sessions[session_id] = pipeline
        logger.info(f"Session registered: {session_id} | Total: {len(self._sessions)}")

    def unregister(self, session_id: str):
        self._sessions.pop(session_id, None)
        logger.info(f"Session removed: {session_id} | Total: {len(self._sessions)}")

    def get(self, session_id: str):
        return self._sessions.get(session_id)

    def count(self):
        return len(self._sessions)
