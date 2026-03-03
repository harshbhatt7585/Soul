from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.agent.scratchpad import ScratchpadStore
from soul.agent.tools import build_default_tools
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig, model_for_mode
from soul.models.llm import LLMHandler

DEFAULT_SOUL_MD = """# Soul

Soul is a personal open-source CLI assistant that runs locally first.

## Identity

- Be pragmatic, concise, and explicit.
- Work with the user's current goal and available tools.
- Do not pretend work happened if no tool or model output supports it.
"""

# TODO: implement Agent class.
class Agent:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._scratchpad = ScratchpadStore(config)
        self._llm_handler = LLMHandler(config)
        self.context = []

    def initialize_state(self, force_identity: bool = False) -> dict[str, object]:
        self._config.soul_home.mkdir(parents=True, exist_ok=True)
        if force_identity or not self._config.soul_path.exists():
            self._config.soul_path.write_text(DEFAULT_SOUL_MD + "\n", encoding="utf-8")
            soul_created = True
        else:
            soul_created = False
    
    def run(self, prompt: str) -> RunResult:
        
        # TODO: implement run function.
        # use LLMHandler to call the model

        # this is kind of pseudo code
        self.context.append(prompt)

        llm = None
        for i in range(max_iterations):
            plan = build_plan_prompt(self.context)
            response = llm(plan)
            tool_calls = parse_tool_calls(response)
            if tool_calls:
                for tool_call in tool_calls:
                    result = self.tools[tool_call.name](tool_call.args)
                    self.context.append(result)
            
            verify = build_verify_prompt(self.context)
            response = llm(verify)
            if not verify_success(response):
                self.context.append(response)
            
            respond = build_respond_prompt(self.context)
            response = llm(respond)
            self.context.append(response)
            return response

            

        pass

    def reset(self) -> None:
        self._scratchpad.reset()
        self.context = []
    
