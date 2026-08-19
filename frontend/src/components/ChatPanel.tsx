import { useState } from 'react'
import { useWorkflowStore } from '../stores/workflowStore'

export default function ChatPanel() {
  const { chatMessages, chatLoading, sendChatMessage, result } = useWorkflowStore()
  const [input, setInput] = useState('')

  if (!result) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatLoading) return
    sendChatMessage(input.trim())
    setInput('')
  }

  const quickQuestions = [
    '用户最痛的3个问题是什么？',
    '总结一下PRD的核心需求',
    'REQ-1 有哪些评论支持？',
    '有哪些需求是假设（证据不足）？',
  ]

  return (
    <div className="card flex flex-col h-[600px]">
      <h3 className="font-semibold mb-3">🤖 Agent Chat</h3>
      <p className="text-xs text-slate-500 mb-3">
        基于当前分析结果提问：需求解释、问题溯源、结果总结等
      </p>

      <div className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
        {chatMessages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-500">你可以直接提问，或点击快捷问题：</p>
            {quickQuestions.map((q) => (
              <button
                key={q}
                onClick={() => sendChatMessage(q)}
                disabled={chatLoading}
                className="block text-left text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded w-full"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        {chatMessages.map((m, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg text-sm ${
              m.role === 'user'
                ? 'bg-blue-100 text-blue-900 ml-8'
                : 'bg-slate-100 text-slate-800 mr-8'
            }`}
          >
            <p className="text-xs font-semibold mb-1">{m.role === 'user' ? 'You' : 'Agent'}</p>
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        {chatLoading && (
          <div className="text-sm text-slate-500 italic">Agent is thinking...</div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the analysis..."
          className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={chatLoading || !input.trim()}
          className="btn-primary px-4 py-2 text-sm"
        >
          Send
        </button>
      </form>
    </div>
  )
}
