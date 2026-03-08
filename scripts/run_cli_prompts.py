from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys

from soul.agent.agent import Agent


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from soul.agent import SoulAgent
from soul.config import AgentConfig, load_agent_config



DEFAULT_PROMPTS = [
    "Hello",
    "How are you?",
    "Give me a short summary of what just happened.",
]

agent_config = load_agent_config()

agent = Agent(
    config=agent_config
)

print(agent.run("hello"))