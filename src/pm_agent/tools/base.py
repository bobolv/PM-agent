from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> str:
        """Run the tool with structured arguments."""
