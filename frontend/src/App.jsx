import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [analysis, setAnalysis] = useState('')
  const [agentUpdates, setAgentUpdates] = useState([])
  const [history, setHistory] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState([])
  const [isChatLoading, setIsChatLoading] = useState(false)

  const handleChatSend = async () => {
    if (!chatInput.trim()) return

    const userMsg = { role: 'user', content: chatInput }
    setChatMessages(prev => [...prev, userMsg])
    setChatInput('')
    setIsChatLoading(true) // Start loading

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg.content })
      })
      const data = await res.json()
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }])
    } catch (err) {
      console.error("Chat error", err)
      setChatMessages(prev => [...prev, { role: 'assistant', content: "Error sending message." }])
    } finally {
      setIsChatLoading(false) // Stop loading
    }
  }

  useEffect(() => {
    // History Fetch
    fetch('http://localhost:8000/history')
      .then(res => res.json())
      .then(data => setHistory(data.history || []))
      .catch(err => console.error("History fetch failed", err))

    // WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws')

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'agent_update') {
          setAgentUpdates(prev => [...prev, {
            agent: data.agent,
            report: data.report,
            tool_data: data.tool_data || {},
          }])
        } else if (data.type === 'final') {
          setAnalysis(data.report)
          setIsProcessing(false)
          setTimeout(() => {
            fetch('http://localhost:8000/history')
              .then(res => res.json())
              .then(d => setHistory(d.history || []))
          }, 1000)
        }
      } catch {
        // fallback for plain-string messages
        setAnalysis(event.data)
        setIsProcessing(false)
      }
    }

    return () => ws.close()
  }, [])

  return (
    <div className="container">
      <header>
        <div className="header-logo">
          <div className="header-logo-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <h1>CV Agent</h1>
        </div>
        <span className="header-badge">Multi-Agent</span>
      </header>

      <main className="split-view">
        {/* Left Column: History */}
        <section className="panel history-panel">
          <h2>History</h2>
          <div className="history-list">
            <ul>
              {history.map((item) => (
                <li key={item[0]}>
                  <div className="history-header">
                    <small>{item[1]}</small>
                  </div>
                  <details>
                    <summary>Analysis #{item[0]}</summary>
                    <div className="history-content">
                      <ReactMarkdown>{item[4]}</ReactMarkdown>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Right Column: Chat/Live Analysis */}
        <section className="panel chat-panel">
          <h2>Chat / Analysis</h2>

          <div className="upload-box">
            <h3>Upload New CV</h3>
            {/* Disable input if processing */}
            <input
              type="file"
              accept=".pdf"
              disabled={isProcessing}
              onChange={async (e) => {
                const file = e.target.files[0]
                if (!file) return

                const formData = new FormData()
                formData.append('file', file)

                setIsProcessing(true)
                setAnalysis('')
                setAgentUpdates([])

                try {
                  const res = await fetch('http://localhost:8000/upload', {
                    method: 'POST',
                    body: formData
                  })
                  const data = await res.json()
                  if (data.status === 'success') {
                    console.log("Upload success")
                    // Keep loading true, waiting for WS message
                  } else {
                    console.error("Upload error", data)
                    setIsProcessing(false) // Stop loading on error
                  }
                } catch (err) {
                  console.error("Upload failed", err)
                  setIsProcessing(false) // Stop loading on error
                }
              }}
            />
          </div>

          <div className="analysis-area">
            {/* Analysis Section */}
            <div className="section-box analysis-result-box">
              <h3 className="section-title">Analysis Result</h3>

              {isProcessing && (
                <div className="loading-indicator">
                  <div className="spinner"></div>
                  <p className="processing-label">Agents analyzing your CV…</p>
                </div>
              )}

              {agentUpdates.length > 0 && (
                <div className="agent-updates">
                  {agentUpdates.map((update, i) => (
                    <div key={i} className="agent-card">
                      <div className="agent-card-header">
                        <span className="agent-check" aria-hidden="true">✓</span>
                        <strong>{update.agent}</strong>
                        {Object.keys(update.tool_data).length > 0 && (
                          <span className="tool-badge">
                            {Object.entries(update.tool_data)
                              .filter(([, v]) => typeof v === 'number' || (Array.isArray(v) && v.length > 0))
                              .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${Array.isArray(v) ? v.length : v}`)
                              .join(' · ')}
                          </span>
                        )}
                      </div>
                      <div className="agent-card-body">
                        <ReactMarkdown>{update.report}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!isProcessing && analysis && (
                <div className="final-result">
                  <h4 className="final-result-label">Synthesized Report</h4>
                  <div className="markdown-box">
                    <ReactMarkdown>{analysis}</ReactMarkdown>
                  </div>
                </div>
              )}

              {!isProcessing && !analysis && agentUpdates.length === 0 && (
                <div className="empty-state">
                  <p>Upload a CV to see the analysis here.</p>
                </div>
              )}
            </div>

            {/* Chat Section */}
            <div className="section-box chat-box">
              <h3 className="section-title">Chat with CV</h3>
              <div className="chat-messages">
                {chatMessages.length === 0 && <p className="chat-placeholder">Ask any question about the CV...</p>}
                {chatMessages.map((msg, index) => (
                  <div key={index} className={`chat-message ${msg.role}`}>
                    <strong>{msg.role === 'user' ? 'You' : 'AI'}: </strong>
                    <div className="message-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                ))}
                {isChatLoading && (
                  <div className="chat-message assistant">
                    <strong>AI: </strong>
                    <div className="message-content">
                      <div className="spinner-small"></div>
                    </div>
                  </div>
                )}
              </div>
              <div className="chat-input-area">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask a question about your CV..."
                  disabled={isProcessing || isChatLoading}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !isProcessing && !isChatLoading) handleChatSend()
                  }}
                />
                <button onClick={handleChatSend} disabled={!chatInput.trim() || isProcessing || isChatLoading}>Send</button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
