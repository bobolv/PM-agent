from pm_agent.agent import DefaultAgent
from pm_agent.config import Settings
from pm_agent.tools import EchoTool, ToolRegistry


def test_default_agent_runs_with_echo_tool() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    agent = DefaultAgent(settings=Settings(), tools=registry)

    assert agent.run("hello") == "pm-agent: hello"
