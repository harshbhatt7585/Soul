from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]


def _normalize_jid(value: str) -> str:
    trimmed = value.strip()
    if "@" in trimmed:
        return trimmed
    digits = "".join(ch for ch in trimmed if ch.isdigit())
    if not digits:
        return ""
    return f"{digits}@s.whatsapp.net"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="queue_whatsapp_message", description="Queue a WhatsApp message for the Soul gateway.")
    parser.add_argument("--to", required=True, help="Phone number or WhatsApp JID to send to.")
    parser.add_argument("--text", help="Message text. If omitted, stdin is used.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        print("Error: missing message text", file=sys.stderr)
        return 1

    to = _normalize_jid(args.to)
    if not to:
        print("Error: invalid destination", file=sys.stderr)
        return 1

    outbox_dir = ROOT / ".soul" / "gateway" / "outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "to": to,
        "text": text,
        "created_at": datetime.now(UTC).isoformat(),
        "id": str(uuid4()),
    }
    path = outbox_dir / f"{payload['created_at'].replace(':', '-')}-{payload['id']}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
