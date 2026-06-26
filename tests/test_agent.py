from pm_agent.agent import DefaultAgent
from pm_agent.config import Settings, get_llm_api_key, get_llm_base_url, get_llm_model
from pm_agent.tools import EchoTool, ToolRegistry


def test_default_agent_runs_with_echo_tool() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    agent = DefaultAgent(settings=Settings(_env_file=None), tools=registry)

    assert agent.run("hello") == "pm-agent: hello"


def test_volcengine_provider_resolves_doubao_defaults() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="volcengine",
        VOLCENGINE_API_KEY="test-key",
    )

    assert get_llm_base_url(settings) == "https://ark.cn-beijing.volces.com/api/v3"
    assert get_llm_model(settings) == "doubao-seed-2-1-pro-260628"
    assert get_llm_api_key(settings) == "test-key"
