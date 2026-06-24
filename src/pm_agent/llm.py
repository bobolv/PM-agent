from dataclasses import dataclass

from openai import OpenAI

from pm_agent.config import Settings


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str


class LLMClient:
    def generate(self, request: LLMRequest) -> str:
        raise NotImplementedError


class OpenAICompatibleClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key or "missing-key",
            base_url=settings.llm_base_url,
        )

    def generate(self, request: LLMRequest) -> str:
        if not self.settings.openai_api_key:
            return offline_markdown_response(request)

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


def offline_markdown_response(request: LLMRequest) -> str:
    return (
        "# 离线草稿\n\n"
        "当前未配置 `OPENAI_API_KEY`，系统已根据提示词生成占位草稿。\n\n"
        "## 生成要求摘要\n\n"
        f"{request.user_prompt[:2000]}\n\n"
        "## 后续处理\n\n"
        "- 配置模型地址和密钥后可重新生成正式文档。\n"
        "- 建议先完善项目任务、阶段产物和模板大纲。\n"
    )
