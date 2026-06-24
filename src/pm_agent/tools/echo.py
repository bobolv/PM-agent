from typing import Any

from pm_agent.tools.base import Tool


class EchoTool(Tool):
    name = "echo"
    description = "Return the text argument unchanged."

    def run(self, arguments: dict[str, Any]) -> str:
        return str(arguments.get("text", ""))
