from abc import ABC, abstractmethod


class Agent(ABC):
    @abstractmethod
    def run(self, prompt: str) -> str:
        """Run the agent with a user prompt."""
