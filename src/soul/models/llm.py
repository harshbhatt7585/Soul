from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import AgentConfig


# TODO: implement LLMHandler, this will handle llm calling.
class LLMHandler:
    def __init__(self, config: AgentConfig) -> None:
        pass
