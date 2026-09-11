"""Session and conversation history persistence for Spiritus harness."""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SESSIONS_DIR = Path(__file__).parent.parent / ".sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class SessionStore:
    def __init__(self, base_dir: Path = SESSIONS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        clean_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not clean_id:
            clean_id = "default"
        return self.base_dir / f"{clean_id}.json"

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        for file in self.base_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get("id", file.stem),
                    "title": data.get("title", "Untitled Session"),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", 0),
                    "turn_count": len(data.get("turns", [])),
                })
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_session(self, session_data: Dict[str, Any]) -> None:
        session_id = session_data.get("id", "default")
        path = self._get_session_path(session_id)
        session_data["updated_at"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

    def append_turn(self, session_id: str, turn: Dict[str, Any]) -> None:
        sess = self.get_session(session_id)
        if not sess:
            sess = {
                "id": session_id,
                "title": turn.get("content", "New Session")[:36],
                "created_at": time.time(),
                "updated_at": time.time(),
                "turns": [],
            }
        sess.setdefault("turns", []).append(turn)
        sess["updated_at"] = time.time()
        self.save_session(sess)

    def delete_session(self, session_id: str) -> bool:
        path = self._get_session_path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception:
                return False
        return False
