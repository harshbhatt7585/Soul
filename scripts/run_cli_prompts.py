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

response = agent.run("hello", stream=True, on_chunk=lambda chunk: print(chunk, end="", flush=True))
print()
reasoning = response.meta.get("reasoning", "")
if reasoning:
    print("reasoning:")
    print(reasoning)
