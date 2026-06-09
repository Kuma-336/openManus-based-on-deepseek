'use client'

import { useState, useCallback } from 'react'
import TaskInput from './components/TaskInput'
import ExecutionStream, { StreamEvent } from './components/ExecutionStream'
import HistorySidebar from './components/HistorySidebar'
import ReportPreview from './components/ReportPreview'

export default function Home() {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [finalReport, setFinalReport] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  /** 提交任务：调用 POST /api/run，消费 SSE 流并追加事件 */
  const handleSubmit = useCallback(
    async (prompt: string, mode: string) => {
      setEvents([])
      setFinalReport(null)
      setIsStreaming(true)

      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, mode, session_id: sessionId }),
        })

        if (!res.body) return
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          // SSE 每条消息以 \n\n 结尾，逐行解析
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const raw = line.slice(6).trim()
            if (!raw) continue
            try {
              const event: StreamEvent = JSON.parse(raw)
              setEvents((prev) => [...prev, event])
              if (event.type === 'done') setFinalReport(event.content)
            } catch {
              // 忽略非 JSON 行
            }
          }
        }
      } catch (err) {
        setEvents((prev) => [
          ...prev,
          { type: 'error', content: String(err) },
        ])
      } finally {
        setIsStreaming(false)
      }
    },
    [sessionId]
  )

  /** 点击历史会话：从 GET /api/history/{id} 加载消息并展示 */
  const handleSelectSession = useCallback(async (sid: string) => {
    setSessionId(sid)
    setFinalReport(null)
    try {
      const res = await fetch(`/api/history/${sid}`)
      const msgs: Array<{ role: string; content: string | null }> = await res.json()

      const loaded: StreamEvent[] = msgs
        .filter((m) => (m.role === 'assistant' || m.role === 'tool') && m.content)
        .map((m) => ({
          type: m.role === 'tool' ? 'observation' : 'thought',
          content: m.content!,
        }))
      setEvents(loaded)

      // 将最后一条 assistant 消息作为报告
      const last = [...msgs].reverse().find((m) => m.role === 'assistant' && m.content)
      if (last) setFinalReport(last.content!)
    } catch {
      // 加载失败静默处理
    }
  }, [])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 左侧历史侧栏 */}
      <HistorySidebar onSelectSession={handleSelectSession} activeSession={sessionId} />

      {/* 主内容区 */}
      <main className="flex-1 flex flex-col overflow-hidden p-4 gap-4">
        {/* 任务输入 */}
        <TaskInput onSubmit={handleSubmit} isLoading={isStreaming} />

        {/* 执行流（可滚动） */}
        <div className="flex-1 overflow-y-auto">
          <ExecutionStream events={events} isStreaming={isStreaming} />
        </div>

        {/* 最终报告（有内容时才显示） */}
        {finalReport && <ReportPreview content={finalReport} />}
      </main>
    </div>
  )
}
