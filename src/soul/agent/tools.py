from abc import ABC, abstractmethod

class Tools(ABC):
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def __call__(self):
        raise NotImplementedError
    
