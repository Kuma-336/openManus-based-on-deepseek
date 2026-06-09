'use client'

import { useEffect, useRef } from 'react'

export type StreamEvent = { type: string; content: string }

/** 每种事件类型对应的标签文字和配色 */
const TYPE_STYLES: Record<string, { label: string; border: string; tag: string; text: string }> = {
  thought:     { label: '思考', border: 'border-indigo-500/30', tag: 'bg-indigo-500/20 text-indigo-300', text: 'text-gray-200' },
  tool_call:   { label: '工具', border: 'border-purple-500/30', tag: 'bg-purple-500/20 text-purple-300', text: 'text-gray-200' },
  observation: { label: '观察', border: 'border-green-500/30',  tag: 'bg-green-500/20 text-green-300',   text: 'text-gray-300' },
  done:        { label: '完成', border: 'border-blue-500/30',   tag: 'bg-blue-500/20 text-blue-300',     text: 'text-gray-200' },
  error:       { label: '错误', border: 'border-red-500/30',    tag: 'bg-red-500/20 text-red-300',       text: 'text-red-200'  },
}

interface Props {
  events: StreamEvent[]
  isStreaming: boolean
}

/** 实时流式渲染 Agent 每步的 Thought / Action / Observation */
export default function ExecutionStream({ events, isStreaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // 新事件到达时自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  if (events.length === 0 && !isStreaming) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-600 text-sm">
        任务执行过程将在这里实时显示
      </div>
    )
  }

  return (
    <div className="space-y-3 pb-2">
      {events.map((event, i) => {
        const style = TYPE_STYLES[event.type] ?? TYPE_STYLES.thought
        return (
          <div
            key={i}
            className={`rounded-lg border bg-[#1a1a1a] p-4 ${style.border}`}
          >
            {/* 类型标签 */}
            <span className={`inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded mb-3 ${style.tag}`}>
              {style.label}
            </span>
            {/* 内容：等宽字体，保留空白 */}
            <pre className={`text-sm whitespace-pre-wrap break-words font-mono leading-relaxed ${style.text}`}>
              {event.content}
            </pre>
          </div>
        )
      })}

      {/* 执行中动画 */}
      {isStreaming && (
        <div className="flex items-center gap-2 text-gray-500 text-sm px-1 py-2">
          <span className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
          Agent 正在执行…
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
