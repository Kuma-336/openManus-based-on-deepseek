import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OpenManus',
  description: 'AI Agent Web UI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className="bg-[#0f0f0f] text-gray-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
