from pm_agent.agent.base import Agent
from pm_agent.config import Settings
from pm_agent.tools import ToolRegistry


class DefaultAgent(Agent):
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools

    def run(self, prompt: str) -> str:
        echo_tool = self.tools.get("echo")
        if echo_tool is None:
            return f"{self.settings.app_name}: {prompt}"

        result = echo_tool.run({"text": prompt})
        return f"{self.settings.app_name}: {result}"
