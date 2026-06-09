'use client'

import { useState, FormEvent } from 'react'

interface Props {
  onSubmit: (prompt: string, mode: string) => void
  isLoading: boolean
}

/** 任务输入区：文本框 + 模式选择 + 提交按钮 */
export default function TaskInput({ onSubmit, isLoading }: Props) {
  const [prompt, setPrompt] = useState('')
  const [mode, setMode] = useState('single')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    onSubmit(prompt.trim(), mode)
    setPrompt('')
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-[#1a1a1a] rounded-xl p-4 border border-[#2a2a2a] shrink-0"
    >
      {/* 模式选择 */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-gray-500 font-medium">执行模式</span>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          disabled={isLoading}
          className="bg-[#0f0f0f] border border-[#2a2a2a] text-gray-300 rounded-lg px-3 py-1.5 text-xs outline-none focus:border-indigo-500 transition-colors disabled:opacity-50"
        >
          <option value="single">单 Agent</option>
          <option value="planning">PlanningFlow</option>
        </select>
      </div>

      {/* 输入框 + 提交按钮 */}
      <div className="flex gap-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit(e as unknown as FormEvent)
            }
          }}
          placeholder="输入你的任务目标... (Enter 提交，Shift+Enter 换行)"
          rows={3}
          disabled={isLoading}
          className="flex-1 bg-[#0f0f0f] border border-[#2a2a2a] text-gray-100 rounded-lg px-4 py-3 text-sm font-mono outline-none focus:border-indigo-500 resize-none placeholder-gray-600 transition-colors disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isLoading || !prompt.trim()}
          className="px-6 self-end py-3 rounded-lg text-sm font-medium text-white
            bg-gradient-to-r from-indigo-600 to-purple-600
            hover:from-indigo-500 hover:to-purple-500
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-200"
        >
          {isLoading ? '执行中…' : '运行'}
        </button>
      </div>
    </form>
  )
}
