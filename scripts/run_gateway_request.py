from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from soul.agent.agent import Agent
from soul.config import load_agent_config


AGENT_LOG = ROOT / ".soul" / "gateway" / "logs" / "agent.log"


def _append_agent_log(entry: dict[str, object]) -> None:
    AGENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AGENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True))
        handle.write("\n")


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "missing request payload"}), file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid request payload: {exc}"}), file=sys.stderr)
        return 1

    text = str(payload.get("text", "")).strip()
    if not text:
        print(json.dumps({"error": "missing text"}), file=sys.stderr)
        return 1

    config = load_agent_config(ROOT)
    agent = Agent(config=config)
    stdout_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            result = agent.run(text)
    except Exception as exc:  # pragma: no cover - bridge failure path
        _append_agent_log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channel": payload.get("channel", ""),
                "sender_jid": payload.get("sender_jid", ""),
                "message_id": payload.get("message_id", ""),
                "text": text,
                "status": "error",
                "error": repr(exc),
                "debug_stdout": stdout_buffer.getvalue().strip(),
            }
        )
        print(json.dumps({"error": f"agent run failed: {exc}"}), file=sys.stderr)
        return 1

    _append_agent_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": payload.get("channel", ""),
            "sender_jid": payload.get("sender_jid", ""),
            "message_id": payload.get("message_id", ""),
            "text": text,
            "reply": result.reply,
            "meta": result.meta,
            "debug_stdout": stdout_buffer.getvalue().strip(),
        }
    )

    print(
        json.dumps(
            {
                "reply": result.reply,
                "meta": result.meta,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
