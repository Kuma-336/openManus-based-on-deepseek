'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Props {
  content: string
}

/** 报告预览区：将 Agent 最终输出的 Markdown 渲染为富文本 */
export default function ReportPreview({ content }: Props) {
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 shrink-0 max-h-72 overflow-y-auto">
      <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-4">
        最终报告
      </h2>
      <div className="prose prose-invert prose-sm max-w-none
        prose-headings:text-gray-200 prose-p:text-gray-300
        prose-a:text-indigo-400 prose-code:text-purple-300
        prose-pre:bg-[#0f0f0f] prose-pre:border prose-pre:border-[#2a2a2a]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}
