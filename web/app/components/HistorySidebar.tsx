'use client'

import { useEffect, useState } from 'react'

interface Session {
  session_id: string
  started_at: string
  msg_count: number
  preview: string
}

interface Props {
  onSelectSession: (sessionId: string) => void
  activeSession: string | null
}

/** 历史记录侧栏：从 GET /api/history 加载，点击可查看会话详情 */
export default function HistorySidebar({ onSelectSession, activeSession }: Props) {
  const [sessions, setSessions] = useState<Session[]>([])

  // 组件挂载时拉取历史列表
  useEffect(() => {
    fetch('/api/history')
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {})
  }, [])

  return (
    <aside className="w-60 bg-[#1a1a1a] border-r border-[#2a2a2a] flex flex-col h-full shrink-0">
      {/* 标题 */}
      <div className="px-4 py-4 border-b border-[#2a2a2a]">
        <h1 className="text-sm font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
          OpenManus
        </h1>
        <p className="text-[11px] text-gray-600 mt-0.5">历史任务</p>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto py-1">
        {sessions.length === 0 ? (
          <p className="text-xs text-gray-600 px-4 py-4">暂无历史记录</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => onSelectSession(s.session_id)}
              className={`w-full text-left px-4 py-3 hover:bg-[#222] transition-colors border-l-2 ${
                activeSession === s.session_id
                  ? 'border-indigo-500 bg-[#222]'
                  : 'border-transparent'
              }`}
            >
              <p className="text-xs text-gray-300 truncate leading-snug">
                {s.preview || '（无内容预览）'}
              </p>
              <p className="text-[10px] text-gray-600 mt-1">
                {s.started_at.slice(0, 16).replace('T', ' ')} · {s.msg_count} 条
              </p>
            </button>
          ))
        )}
      </div>
    </aside>
  )
}
