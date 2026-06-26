from dataclasses import dataclass

from openai import OpenAI, OpenAIError

from pm_agent.config import Settings, get_llm_api_key, get_llm_base_url, get_llm_model


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str


class LLMClient:
    def generate(self, request: LLMRequest) -> str:
        raise NotImplementedError


class ModelInvocationError(RuntimeError):
    pass


class OpenAICompatibleClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = get_llm_api_key(settings)
        self.base_url = get_llm_base_url(settings)
        self.model = get_llm_model(settings)
        self.client = OpenAI(
            api_key=self.api_key or "missing-key",
            base_url=self.base_url,
        )

    def generate(self, request: LLMRequest) -> str:
        if not self.api_key:
            return offline_markdown_response(request, self.settings.llm_provider)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.settings.llm_temperature,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
            )
        except OpenAIError as exc:
            raise ModelInvocationError(f"模型调用失败：{exc}") from exc
        return response.choices[0].message.content or ""


def offline_markdown_response(request: LLMRequest, provider: str = "openai") -> str:
    key_name = "VOLCENGINE_API_KEY" if provider == "volcengine" else "OPENAI_API_KEY"
    return (
        "# 离线草稿\n\n"
        f"当前未配置 `{key_name}`，系统已根据提示词生成占位草稿。\n\n"
        "## 生成要求摘要\n\n"
        f"{request.user_prompt[:2000]}\n\n"
        "## 后续处理\n\n"
        "- 配置模型地址和密钥后可重新生成正式文档。\n"
        "- 建议先完善项目任务、阶段产物和模板大纲。\n"
    )
