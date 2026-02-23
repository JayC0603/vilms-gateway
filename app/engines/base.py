# app/engines/base.py
from abc import ABC, abstractmethod

class BaseViLMSEngine(ABC):
    @abstractmethod
    async def chat_completion(self, payload: dict):
        pass
