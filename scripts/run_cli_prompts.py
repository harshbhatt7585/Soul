from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from soul.agent.agent import Agent
from soul.config import load_agent_config

DEFAULT_PROMPTS = [
    "Hello",
    "How are you?",
    "Give me a short summary of what just happened.",
]

agent_config = load_agent_config()

agent = Agent(
    config=agent_config
)

printed_reasoning_header = False
printed_content_header = False


def _print_reasoning(chunk: str) -> None:
    global printed_reasoning_header
    if not printed_reasoning_header:
        print("reasoning:")
        printed_reasoning_header = True
    print(chunk, end="", flush=True)


def _print_content(chunk: str) -> None:
    global printed_content_header
    if not printed_content_header:
        if printed_reasoning_header:
            print()
        print("content:")
        printed_content_header = True
    print(chunk, end="", flush=True)


response = agent.run(
    "What is the stock of google?",
    stream=True,
    on_chunk=_print_content,
    on_reasoning_chunk=_print_reasoning,
)
print()
