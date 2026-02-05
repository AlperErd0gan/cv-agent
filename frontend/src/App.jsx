import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [analysis, setAnalysis] = useState('')
  const [history, setHistory] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)

  useEffect(() => {
    // History Fetch
    fetch('http://localhost:8000/history')
      .then(res => res.json())
      .then(data => setHistory(data.history || []))
      .catch(err => console.error("History fetch failed", err))

    // WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws')

    ws.onmessage = (event) => {
      console.log("New message:", event.data)
      setAnalysis(event.data)
      setIsProcessing(false) // Stop loading when we get a message
      // Refresh history slightly later
      setTimeout(() => {
        fetch('http://localhost:8000/history')
          .then(res => res.json())
          .then(data => setHistory(data.history || []))
      }, 1000)
    }

    return () => ws.close()
  }, [])

  return (
    <div className="container">
      <header>
        <h1>CV Agent 🕵️‍♂️</h1>
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

                setIsProcessing(true) // Start loading
                setAnalysis('') // Clear previous analysis

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
            {isProcessing && (
              <div className="loading-indicator">
                <div className="spinner"></div>
                <p>Analyzing CV with AI Model...</p>
              </div>
            )}

            {!isProcessing && analysis && (
              <div className="markdown-box">
                <ReactMarkdown>{analysis}</ReactMarkdown>
              </div>
            )}

            {!isProcessing && !analysis && (
              <div className="empty-state">
                <p>Upload a CV to start the analysis.</p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
