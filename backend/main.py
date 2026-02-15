from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from watcher import process_cv, init_db, get_last_feedback, chat_with_cv, get_last_state, DB_PATH, PDF_PATH
import threading
import os
import sqlite3
from pydantic import BaseModel

# Initial Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")
init_db()

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

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    loop = asyncio.get_running_loop()
    t = threading.Thread(target=run_watcher_loop, args=(loop,), daemon=True)
    t.start()
    yield
    # Shutdown logic (if any) can go here

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

@app.post("/upload")
async def upload_cv(file: UploadFile = File(...)):
    """Upload a new CV PDF. This will overwrite the existing file and trigger the watcher."""
    try:
        # Save the file to the path monitored by watcher
        content = await file.read()
        with open(PDF_PATH, "wb") as f:
            f.write(content)
        
        logger.info(f"New CV uploaded to {PDF_PATH}")
        return {"status": "success", "message": "CV uploaded and analysis triggered."}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return {"status": "error", "message":str(e)}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """Chat with the current CV."""
    try:
        _, cv_text = get_last_state()
        if not cv_text:
            return {"response": "CV henüz yüklenmedi veya analiz edilmedi."}
        
        response = chat_with_cv(request.message, cv_text)
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {"response": "Chat sırasında bir hata oluştu."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
