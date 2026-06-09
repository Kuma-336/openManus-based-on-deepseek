"""
main.py — FastAPI 后端入口。

接口：
  POST /run        启动任务，SSE 流式返回 Agent 执行过程
  GET  /history    读取 SQLite 历史会话列表
  GET  /history/{session_id}  读取某次会话的消息详情

启动方式（在 OpenManus 根目录）：
  uvicorn api.main:app --reload --port 8000
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.memory.persistent import PersistentMemory
from api.runner import run_agent_stream

app = FastAPI(title="OpenManus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    prompt: str
    mode: str = "single"          # "single" | "planning"
    session_id: Optional[str] = None


@app.post("/run")
async def run_task(req: RunRequest):
    """启动 Agent 任务，以 SSE 流式返回每步执行事件。"""
    return StreamingResponse(
        run_agent_stream(req.prompt, req.mode, req.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁用 Nginx 缓冲，确保实时推送
        },
    )


@app.get("/history")
async def get_history():
    """返回最近 20 条历史会话摘要。"""
    return PersistentMemory.list_sessions(limit=20)


@app.get("/history/{session_id}")
async def get_session_detail(session_id: str):
    """返回指定会话的全部消息（role + content）。"""
    messages = PersistentMemory.load_session(session_id)
    return [{"role": m.role, "content": m.content} for m in messages]


@app.get("/health")
async def health():
    return {"status": "ok"}
