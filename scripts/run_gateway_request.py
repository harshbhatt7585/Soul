from __future__ import annotations

import contextlib
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
    with contextlib.redirect_stdout(io.StringIO()):
        result = agent.run(text)

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
