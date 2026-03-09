# Soul WhatsApp Gateway

This gateway mirrors the OpenClaw-style pattern:

- a long-lived WhatsApp Web session owned by one gateway process
- Soul remains the agent runtime
- inbound messages are handed to Soul
- outbound messages are picked up from an outbox queue

## Architecture

Components:

- `src/index.js`: gateway entrypoint
- `src/whatsapp-gateway.js`: Baileys socket lifecycle and event handling
- `src/soul-bridge.js`: invokes Soul through a narrow Python bridge
- `src/outbox.js`: polls `.soul/gateway/outbox` and sends queued outbound messages
- `scripts/run_gateway_request.py`: single inbound request -> Soul reply
- `scripts/queue_whatsapp_message.py`: queue outbound messages for the gateway

Runtime layout:

- `.soul/gateway/auth`: Baileys auth/session state
- `.soul/gateway/outbox`: outbound messages waiting to send
- `.soul/gateway/sent`: sent outbound message records
- `.soul/gateway/failed`: failed outbound message records

## Install

From the repo root:

```bash
cd gateway
npm install
```

## Run

Start the gateway:

```bash
./scripts/start_whatsapp_gateway.sh
```

On first run, scan the QR code shown in the terminal.

## Queue an outbound message

```bash
python3 scripts/queue_whatsapp_message.py --to 919999999999 --text "AI digest is ready"
```

The running gateway daemon will pick it up and send it.

## Config

Environment variables:

- `SOUL_GATEWAY_ALLOWED_FROM`: comma-separated WhatsApp JIDs allowed to message the bot
- `SOUL_GATEWAY_AUTO_REPLY`: `true` or `false`
- `SOUL_GATEWAY_ALLOW_GROUPS`: `true` or `false`
- `SOUL_GATEWAY_OUTBOX_POLL_MS`: outbound polling interval
- `SOUL_GATEWAY_PAIRING_PHONE`: optional phone number for pairing-code login without QR
- `SOUL_GATEWAY_PYTHON`: Python executable for the Soul bridge
- `SOUL_GATEWAY_BRIDGE_SCRIPT`: Python bridge script path
- `SOUL_WHATSAPP_DEFAULT_TO`: optional default destination for your own higher-level scripts

## Notes

- This uses WhatsApp Web through Baileys, not the official WhatsApp Business API.
- The gateway should run as a long-lived process. Use `pm2`, `launchd`, `systemd`, or another daemon manager in practice.
- Cron should enqueue outbound work, not restart the WhatsApp socket every minute.
