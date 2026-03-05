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


# TODO: implement Agent class.
class Agent:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._scratchpad = ScratchpadStore(config)
        self._llm_handler = LLMHandler(config)
        self.context = []        
    
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
    
