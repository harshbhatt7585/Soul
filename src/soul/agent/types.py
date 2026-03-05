from abc import ABC, abstractmethod
from typing import Any

class ToolCall(ABC):
    def __init__(self, name: str, args: dict[str, Any]):
        self.name = name
    
    @abstractmethod
    def __call__(self) -> Any:
        raise NotImplementedError

# TODO: implement WebSearchToolCall class.
class WebSearchToolCall(ToolCall):
    def __init__(self, query: str):
        super().__init__()

    def __call__(self) -> Any:
        pass


# TODO: implement FileReadToolCall class.
class FileReadToolCall(ToolCall):  
    def __init__(self, file_path: str):
        super().__init__()

    def __call__(self) -> Any:
        pass



# TODO: implement MemoryRecallToolCall class
class MemoryRecallToolCall(ToolCall):
    def __init__(self):
        super().__init__()

    def __call__(self) -> Any:
        pass


# TODO: implement MemoryWriteToolCall class
class MemoryWriteToolCall(ToolCall):
    def __init__(self, content: str):
        super().__init__()

    def __call__(self) -> Any:
        pass
