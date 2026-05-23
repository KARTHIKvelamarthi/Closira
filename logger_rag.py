import json
import os
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ESCALATION_LOG_FILE = LOGS_DIR / "escalation_log_rag.json"
SUMMARY_LOG_FILE = LOGS_DIR / "session_summaries_rag.json"


def _load_log(path: Path) -> list:
    if path.exists():
        with open(path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _save_log(path: Path, data: list):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def log_escalation(
    session_id: str,
    reason: str,
    trigger_message: str,
    stage: str,
    confidence: float
):
    """Append an escalation event to escalation_log_rag.json."""
    entries = _load_log(ESCALATION_LOG_FILE)
    entries.append({
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "stage_at_escalation": stage,
        "confidence_score": round(confidence, 2),
        "reason": reason,
        "trigger_message": trigger_message
    })
    _save_log(ESCALATION_LOG_FILE, entries)
    print(f"\n  [LOG] Escalation recorded → {reason}")


def log_summary(session_id: str, summary: dict):
    """Append a session summary to session_summaries_rag.json."""
    entries = _load_log(SUMMARY_LOG_FILE)
    entries.append(summary)
    _save_log(SUMMARY_LOG_FILE, entries)
    print(f"\n  [LOG] Session summary saved → session {session_id}")
