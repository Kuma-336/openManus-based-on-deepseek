# OpenManus 改动记录

本文档记录本次开发会话对 OpenManus 所做的全部改动。

---

## 1. 多轮对话支持（`main.py`）

**问题**：原版每次运行只接受一条 prompt，处理完即退出，无法连续对话。

**改动**：
- 将单次 `input()` 改为 `while True` 交互循环
- 输入 `exit` 或 `quit` 退出，支持空行跳过
- 命令行 `--prompt` 参数保持原有单次执行行为
- 同一个 `agent` 实例在整个会话中复用，上下文跨轮保留

---

## 2. 修复 `ask_human` 与外层循环冲突（`app/prompt/manus.py`）

**问题**：agent 在回答完问题后，会主动调用 `ask_human` 工具等待用户输入，与外层 `while True` 循环的 `input()` 产生双重拦截，导致对话错乱。

**改动**：在 `NEXT_STEP_PROMPT` 中补充明确指令：

> 回答完用户消息后，直接调用 `terminate`。禁止用 `ask_human` 征求下一个任务——用户会自行发起下一条消息。`ask_human` 仅用于执行当前任务时真正缺少必要参数的情况。

---

## 3. SQLite 持久化记忆（新增 `app/memory/`）

**问题**：原版每次运行都是"失忆"的，没有跨会话的历史记录。

**新增文件**：
- `app/memory/__init__.py`
- `app/memory/persistent.py`

**数据库**：`workspace/memory.db`（自动创建）

**两张表**：

| 表名 | 用途 |
|------|------|
| `task_history` | 存储每次会话的消息记录（session_id / role / content / tool_calls / timestamp） |
| `search_cache` | 缓存搜索结果，默认 TTL 24 小时，按 `query + num_results` 哈希去重 |

**`PersistentMemory` 提供的方法**：

```python
PersistentMemory.save_messages(session_id, messages)   # 追加保存新消息
PersistentMemory.load_session(session_id)               # 加载历史消息
PersistentMemory.list_sessions(limit=10)                # 列出最近会话摘要
PersistentMemory.get_search_cache(query, num_results)   # 查询缓存
PersistentMemory.set_search_cache(query, num_results, results)  # 写入缓存
```

**`main.py` 集成**：
- 启动时显示历史会话列表，输入序号可续接上次对话
- 每轮 `agent.run()` 结束后自动保存消息到 SQLite

---

## 4. 搜索结果缓存（`app/tool/web_search.py`）

**改动**：在 `WebSearch.execute()` 中加入缓存逻辑：

- 执行前先查 `search_cache`，命中则直接返回，跳过网络请求
- 成功获取结果后写入缓存（TTL 24 小时）
- `fetch_content=True` 模式跳过缓存（网页正文内容会变化）

---

## 5. Web UI（新增 `api/` + `web/`）

### 后端：FastAPI（`api/`）

**文件**：
- `api/__init__.py`
- `api/runner.py` — `StreamingManus` + SSE 异步生成器
- `api/main.py` — FastAPI 路由

**接口**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/run` | 启动任务，SSE 流式返回每步执行事件 |
| `GET` | `/history` | 读取历史会话列表（最近 20 条） |
| `GET` | `/history/{session_id}` | 读取指定会话的消息详情 |

**SSE 事件格式**：

```json
{"type": "thought",      "content": "Agent 的思考内容"}
{"type": "tool_call",    "content": "**tool_name**\n```json\n{args}\n```"}
{"type": "observation",  "content": "工具执行结果"}
{"type": "done",         "content": "最终回答（Markdown）"}
{"type": "error",        "content": "错误信息"}
```

**`StreamingManus`**：继承 `Manus`，重写 `think()` / `act()`，在每步结束后扫描新增消息并推入 `asyncio.Queue`，实现非侵入式流式传输。

### 前端：Next.js + Tailwind CSS（`web/`）

**目录结构**：

```
web/
├── package.json
├── next.config.js        # /api/* 反向代理到 :8000
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── app/
    ├── globals.css
    ├── layout.tsx
    ├── page.tsx                        # 主页面，管理全局状态
    └── components/
        ├── TaskInput.tsx               # 任务输入框 + 模式选择
        ├── ExecutionStream.tsx         # 彩色标签流式展示
        ├── HistorySidebar.tsx          # 历史会话侧栏
        └── ReportPreview.tsx           # Markdown 渲染（react-markdown）
```

**设计风格**：
- 背景 `#0f0f0f`，卡片 `#1a1a1a`，强调色蓝紫渐变
- 执行流各类型配色：思考=靛蓝、工具=紫色、观察=绿色、完成=蓝色、错误=红色
- 代码区等宽字体，细滚动条

---

## 启动方式

```bash
# 后端（OpenManus 根目录）
uvicorn api.main:app --reload --port 8000

# 前端（新开终端）
cd web
npm install
npm run dev
# 访问 http://localhost:3000
```

---

## 改动文件汇总

| 文件 | 类型 | 说明 |
|------|------|------|
| `main.py` | 修改 | 多轮对话循环 + 历史会话加载 + 自动保存 |
| `app/prompt/manus.py` | 修改 | 修复 ask_human 误用问题 |
| `app/tool/web_search.py` | 修改 | 搜索结果缓存 |
| `app/memory/__init__.py` | 新增 | 模块入口 |
| `app/memory/persistent.py` | 新增 | SQLite 持久化记忆 |
| `api/__init__.py` | 新增 | 后端包入口 |
| `api/runner.py` | 新增 | StreamingManus + SSE 生成器 |
| `api/main.py` | 新增 | FastAPI 后端 |
| `web/` | 新增 | Next.js 前端（15 个文件） |
