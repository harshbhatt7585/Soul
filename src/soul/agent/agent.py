# TODO: Implement Agent Class
from os import name
from agent.llm import LLMHandler


class Agent:
    def __init__(
        name: str,
        
    ):
    self.name = name
    
    # TODO: Implemet handling messages
    self.messages = []


    self.llm = LLMHandler()


    def run(self, prompt):
        pass