"""
OpenManus — Function Calling 核心代码示例
这段代码展示了一个完整的 ReAct (Reasoning + Acting) Agent 中
Function Calling 的核心实现，包含三个层次：

1. BaseTool       — 工具定义与 OpenAI 格式转换
2. ToolCollection — 工具注册与分发执行
3. ToolCallAgent  — Think/Act 循环，与 LLM 交互并执行 tool_calls
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 层一：Tool 定义
# 文件: app/tool/base.py
# ──────────────────────────────────────────────

class ToolResult(BaseModel):
    """工具执行结果的统一格式"""
    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)

    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)

    def __str__(self):
        return f"Error: {self.error}" if self.error else str(self.output)


class BaseTool(ABC, BaseModel):
    """所有工具的基类，实现 OpenAI function calling 格式"""
    name: str
    description: str
    parameters: Optional[dict] = None

    async def __call__(self, **kwargs) -> Any:
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """子类实现具体执行逻辑"""

    def to_param(self) -> Dict:
        """将工具定义转换为 OpenAI function calling 格式，传给 LLM"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,  # JSON Schema
            },
        }


# 示例：一个具体工具的实现
class PythonExecute(BaseTool):
    name: str = "python_execute"
    description: str = "Execute Python code and return the output"
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute",
            }
        },
        "required": ["code"],
    }

    async def execute(self, code: str) -> ToolResult:
        try:
            exec_globals = {}
            exec(code, exec_globals)
            return ToolResult(output="Code executed successfully")
        except Exception as e:
            return ToolResult(error=str(e))


# ──────────────────────────────────────────────
# 层二：Tool 注册与分发
# 文件: app/tool/tool_collection.py
# ──────────────────────────────────────────────

class ToolCollection:
    """管理多个工具的集合，负责注册与统一分发执行"""

    def __init__(self, *tools: BaseTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def to_params(self) -> List[Dict[str, Any]]:
        """将所有工具转为 API 参数格式，直接传入 LLM 的 tools 字段"""
        return [tool.to_param() for tool in self.tools]

    async def execute(self, *, name: str, tool_input: Dict[str, Any] = None) -> ToolResult:
        """按名称分发执行对应工具"""
        tool = self.tool_map.get(name)
        if not tool:
            return ToolResult(error=f"Tool '{name}' is invalid")
        try:
            return await tool(**tool_input)
        except Exception as e:
            return ToolResult(error=str(e))

    def add_tool(self, tool: BaseTool):
        """运行时动态注册新工具（用于 MCP 远程工具热加载）"""
        if tool.name not in self.tool_map:
            self.tools += (tool,)
            self.tool_map[tool.name] = tool
        return self


# ──────────────────────────────────────────────
# 层三：ReAct Agent — Think / Act 循环
# 文件: app/agent/toolcall.py
# ──────────────────────────────────────────────

class ToolCallAgent:
    """
    ReAct 模式的核心 Agent，实现 Function Calling 的完整闭环：

    循环：
        think() → 调用 LLM，传入工具定义，解析返回的 tool_calls
        act()   → 执行 tool_calls，将结果写入对话记忆
    直到 LLM 不再返回 tool_calls（任务完成）或达到 max_steps
    """

    def __init__(self, llm, available_tools: ToolCollection, system_prompt: str = ""):
        self.llm = llm
        self.available_tools = available_tools
        self.system_prompt = system_prompt
        self.memory = []        # 对话记忆（包含 user/assistant/tool 消息）
        self.tool_calls = []    # 当前步骤 LLM 返回的 tool_calls
        self.max_steps = 30

    async def think(self) -> bool:
        """
        Think 阶段：
        1. 将当前对话记忆 + 所有工具定义发送给 LLM
        2. 解析 LLM 返回的 tool_calls
        3. 将 assistant 消息（含 tool_calls）写入记忆
        """
        response = await self.llm.ask_tool(
            messages=self.memory,
            system_msgs=[{"role": "system", "content": self.system_prompt}],
            tools=self.available_tools.to_params(),   # 关键：把工具定义传给 LLM
            tool_choice="auto",                        # auto / required / none
        )

        # 解析 LLM 返回的 tool_calls
        self.tool_calls = response.tool_calls if response and response.tool_calls else []
        content = response.content if response and response.content else ""

        # 将 assistant 消息写入记忆
        assistant_msg = {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ] if self.tool_calls else None,
        }
        self.memory.append(assistant_msg)

        # 有 tool_calls 则进入 act 阶段；否则任务完成
        return bool(self.tool_calls)

    async def act(self) -> str:
        """
        Act 阶段：
        1. 遍历每个 tool_call，解析参数并执行对应工具
        2. 将工具结果作为 tool 角色消息写入记忆（通过 tool_call_id 关联）
        """
        results = []
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            # tool 消息必须携带 tool_call_id，LLM 才能将结果与对应的 tool_call 关联
            tool_msg = {
                "role": "tool",
                "tool_call_id": command.id,
                "name": command.function.name,
                "content": result,
            }
            self.memory.append(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command) -> str:
        """
        执行单个 tool_call：
        - 解析 JSON 参数
        - 通过 ToolCollection 分发到对应工具
        - 统一格式化观测结果返回给 LLM
        """
        name = command.function.name

        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            args = json.loads(command.function.arguments or "{}")
            result = await self.available_tools.execute(name=name, tool_input=args)

            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )
            return observation

        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments for tool '{name}'"
        except Exception as e:
            return f"Error: Tool '{name}' failed — {str(e)}"

    async def run(self, request: str) -> str:
        """主循环：Think → Act，直到完成或超出 max_steps"""
        self.memory.append({"role": "user", "content": request})

        for step in range(self.max_steps):
            should_act = await self.think()
            if not should_act:
                break
            await self.act()

        # 返回最后一条 assistant 消息内容
        for msg in reversed(self.memory):
            if msg["role"] == "assistant" and msg.get("content"):
                return msg["content"]
        return "Task completed."
