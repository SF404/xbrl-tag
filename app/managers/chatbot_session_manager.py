from threading import Lock
from collections import deque
from typing import Dict, Deque, List

MAX_HISTORY = 40

class ChatBotSessionManager:
    def __init__(self):
        self._sessions: Dict[str, Deque[Dict[str,str]]] = {}
        self._lock = Lock()

    def get_history(self, session_id: str) -> List[Dict[str,str]]:
        with self._lock:
            dq = self._sessions.setdefault(session_id, deque(maxlen=MAX_HISTORY))
            return list(dq)

    def append(self, session_id: str, role: str, text: str) -> None:
        with self._lock:
            dq = self._sessions.setdefault(session_id, deque(maxlen=MAX_HISTORY))
            dq.append({"role": role, "text": text})

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

chatbot_session_manager = ChatBotSessionManager()
