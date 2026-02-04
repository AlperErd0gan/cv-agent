from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from watcher import process_cv, init_db, get_last_feedback, DB_PATH
import threading
import os
import sqlite3

# Initial Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")
init_db()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Background Watcher Wrapper
def run_watcher_loop(loop):
    """Background thread to run the watcher logic."""
    import watcher
    from watchdog.observers.polling import PollingObserver as Observer
    from watcher import Handler, PDF_PATH
    
    # Callback wrapper to bridge Thread -> Asyncio
    def callback(message):
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

    watcher.ON_ANALYSIS_COMPLETE = callback
    
    folder = os.path.dirname(PDF_PATH) or "."
    observer = Observer(timeout=3.0)
    observer.schedule(Handler(), folder, recursive=False)
    observer.start()
    logger.info("Background watcher started.")
    observer.join()

# Start Watcher in Background
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    t = threading.Thread(target=run_watcher_loop, args=(loop,), daemon=True)
    t.start()


@app.get("/")
def read_root():
    return {"status": "CV Agent Backend Running"}

@app.get("/history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM history ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    return {"history": rows}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
