"""
runner.py — 封装 Agent 执行，通过 asyncio.Queue 将每步事件流式传出。

StreamingManus 继承 Manus，在 think()/act() 后扫描新增消息并推入队列。
run_agent_stream() 是供 FastAPI 调用的异步生成器，输出 SSE 格式字符串。
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator, Optional

from pydantic import PrivateAttr

from app.agent.manus import Manus
from app.flow.flow_factory import FlowFactory, FlowType
from app.memory.persistent import PersistentMemory


class StreamingManus(Manus):
    """Manus 子类：hook think/act，把每步产生的消息推入 asyncio.Queue。"""

    _queue: Optional[asyncio.Queue] = PrivateAttr(default=None)
    _msg_offset: int = PrivateAttr(default=0)

    def bind_queue(self, q: asyncio.Queue, offset: int = 0) -> None:
        """绑定事件队列，offset 用于跳过历史消息。"""
        self._queue = q
        self._msg_offset = offset

    async def think(self) -> bool:
        result = await super().think()
        await self._push_new_messages()
        return result

    async def act(self) -> str:
        result = await super().act()
        await self._push_new_messages()
        return result

    async def _push_new_messages(self) -> None:
        """将上次检查之后新增的 assistant/tool 消息推入队列。"""
        if self._queue is None:
            return
        new_msgs = self.memory.messages[self._msg_offset:]
        for msg in new_msgs:
            if msg.role == "assistant":
                if msg.content:
                    await self._queue.put({"type": "thought", "content": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        await self._queue.put({
                            "type": "tool_call",
                            "content": f"**{tc.function.name}**\n```json\n{tc.function.arguments}\n```",
                        })
            elif msg.role == "tool":
                content = msg.content or ""
                if len(content) > 2000:
                    content = content[:2000] + "\n\n*（内容过长，已截断）*"
                await self._queue.put({"type": "observation", "content": content})
        self._msg_offset = len(self.memory.messages)


def _sse(event: dict) -> str:
    """将字典序列化为 SSE data 行。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def run_agent_stream(
    prompt: str,
    mode: str = "single",
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    启动 Agent 并以 SSE 格式逐步 yield 执行事件。

    mode="single"   → 直接调用 Manus.run()
    mode="planning" → 通过 PlanningFlow 执行
    """
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    queue: asyncio.Queue = asyncio.Queue()
    agent = await StreamingManus.create()

    # 加载历史消息（若有），并将 offset 设为历史长度，避免重复推送
    history = PersistentMemory.load_session(session_id)
    if history:
        agent.memory.messages = history
    agent.bind_queue(queue, offset=len(agent.memory.messages))

    async def _run_task() -> None:
        try:
            if mode == "planning":
                flow = FlowFactory.create_flow(
                    FlowType.PLANNING,
                    agents={"manus": agent},
                )
                await flow.execute(prompt)
            else:
                await agent.run(prompt)

            # 找最后一条有内容的 assistant 消息作为最终结果
            for msg in reversed(agent.memory.messages):
                if msg.role == "assistant" and msg.content and msg.content.strip():
                    await queue.put({"type": "done", "content": msg.content.strip()})
                    break
        except Exception as e:
            await queue.put({"type": "error", "content": str(e)})
        finally:
            PersistentMemory.save_messages(session_id, agent.memory.messages)
            await agent.cleanup()
            await queue.put(None)  # 结束哨兵

    task = asyncio.create_task(_run_task())

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _sse(event)
    except GeneratorExit:
        task.cancel()
    finally:
        if not task.done():
            task.cancel()
