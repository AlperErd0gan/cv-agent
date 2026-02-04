import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [status, setStatus] = useState('Connecting...')
  const [analysis, setAnalysis] = useState('')
  const [history, setHistory] = useState([])

  useEffect(() => {
    // History Fetch
    fetch('http://localhost:8000/history')
      .then(res => res.json())
      .then(data => setHistory(data.history || []))
      .catch(err => console.error("History fetch failed", err))

    // WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws')

    ws.onopen = () => {
      setStatus('Connected & Watching')
    }

    ws.onmessage = (event) => {
      console.log("New message:", event.data)
      setAnalysis(event.data)
      // Refresh history slightly later
      setTimeout(() => {
        fetch('http://localhost:8000/history')
          .then(res => res.json())
          .then(data => setHistory(data.history || []))
      }, 1000)
    }

    ws.onclose = () => {
      setStatus('Disconnected')
    }

    return () => ws.close()
  }, [])

  return (
    <div className="container">
      <header>
        <h1>CV Agent 🕵️‍♂️</h1>
        <div className={`status ${status.includes('Connected') ? 'online' : 'offline'}`}>
          {status}
        </div>
      </header>

      <main>
        <section className="live-panel">
          <h2>Latest Analysis</h2>

          <div className="upload-box">
            <h3>Upload New CV</h3>
            <input type="file" accept=".pdf" onChange={async (e) => {
              const file = e.target.files[0]
              if (!file) return

              const formData = new FormData()
              formData.append('file', file)

              try {
                const res = await fetch('http://localhost:8000/upload', {
                  method: 'POST',
                  body: formData
                })
                const data = await res.json()
                if (data.status === 'success') {
                  // Optionally clean input or show notification
                  console.log("Upload success")
                } else {
                  console.error("Upload error", data)
                }
              } catch (err) {
                console.error("Upload failed", err)
              }
            }} />
          </div>

          <div className="markdown-box">
            {analysis ? <ReactMarkdown>{analysis}</ReactMarkdown> : <p>Waiting for changes...</p>}
          </div>
        </section>

        <section className="history-panel">
          <h2>History</h2>
          <ul>
            {history.map((item) => (
              <li key={item[0]}>
                <small>{item[1]}</small>
                {/* item[3] is diff_text, item[4] is llm_response. We just show brief or allow expand. */}
                <details>
                  <summary>Analysis #{item[0]}</summary>
                  <div className="history-content">
                    <ReactMarkdown>{item[4]}</ReactMarkdown>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}

export default App
