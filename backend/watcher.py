import os
import time
import difflib
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from pypdf import PdfReader
from langchain_ollama import OllamaLLM
import hashlib
import logging
import requests
import sqlite3
import asyncio

# Callback mechanism
ON_ANALYSIS_COMPLETE = None

# Konfigürasyon
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3")
llm = OllamaLLM(model=MODEL, base_url=OLLAMA_BASE_URL)

# Docker içinde çakışmayı önlemek için /data klasörünü varsayılan yapıyoruz
env_pdf = os.getenv("PDF_PATH", "/data/cv.pdf")
env_db = os.getenv("DB_PATH", "/data/cv_agent.db")

PDF_PATH = os.path.abspath(env_pdf)
DB_PATH = os.path.abspath(env_db)

# Cache dosyalarını PDF'in olduğu yere (root'a) kaydedelim
work_dir = os.path.dirname(PDF_PATH)
CACHE_PATH = os.path.join(work_dir, ".cv_last.txt")
HASH_PATH = os.path.join(work_dir, ".cv_last.sha256")




def init_db():
    """Veritabanını ve tabloyu oluştur."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cv_hash TEXT,
            diff_text TEXT,
            llm_response TEXT,
            full_text TEXT
        )
    ''')
    
    # Migration for existing DBs
    try:
        c.execute('ALTER TABLE history ADD COLUMN full_text TEXT')
    except sqlite3.OperationalError:
        pass # Column likely exists
    
    conn.commit()
    conn.close()


def save_analysis(cv_hash, diff_text, llm_response, full_text):
    """Analiz sonucunu ve metni kaydet."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO history (cv_hash, diff_text, llm_response, full_text) VALUES (?, ?, ?, ?)',
              (cv_hash, diff_text, llm_response, full_text))
    conn.commit()
    conn.close()


def get_last_feedback():
    """En son yapılan yorumu getir."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT llm_response FROM history ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    return row[0] if row else None



def wait_for_ollama():
    """Ollama servisi hazır olana kadar bekle."""
    url = f"{OLLAMA_BASE_URL}/api/tags"
    logger.info(f"Ollama bağlanmaya çalışılıyor: {url}")
    while True:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info("Ollama bağlantısı başarılı!")
                return
        except Exception as e:
            logger.warning(f"Ollama'ya ulaşılamadı ({e}). 5 saniye içinde tekrar denenecek...")
        time.sleep(5)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_to_text(path: str) -> str:
    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        t = p.extract_text() or ""
        # Remove weird hyphenations but KEEP newlines for diffing
        t = t.replace("-\n", "")
        # Do NOT replace \n with space anymore
        if t:
            pages.append(t)
    return "\n\n".join(pages).strip()

def get_last_state():
    """DB'den son hash ve texti getir."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT cv_hash, full_text FROM history ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return "", ""

def make_diff(old: str, new: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm=""
        )
    )

def analyze(diff_text: str, new_text: str, previous_feedback: str = None) -> str:
    original_prompt = f"""
You are an expert Career Coach and Tech Recruiter. The user has modified their CV. 
Your goal is to understand the *intent* behind the changes and provide strategic advice based on the **FULL CONTEXT** of the CV.

FULL CV PREVIEW:
---
{new_text}
---

DIFF (Changes made):
---
{diff_text}
---

TASKS:
0. **DETECTED CHANGES LIST**: Start your response by listing the *exact* changes you see (e.g. "Changed 'Manager' to 'Senior Manager'").
1. **Contextual Analysis**: How does this change fit with the rest of the CV? (e.g. "Adding Python makes sense given your Django experience" OR "Adding Neurosurgery seems random for a Frontend Developer").
2. **Impact Assessment**: Did this change make the CV stronger or weaker? Why?
3. **Critical Review**: Are there new issues? (Typos, weak verbs, inconsistencies).
4. **Strategic Advice**: What is the ONE investigation they should do next?
"""
    
    if previous_feedback:
        prompt = f"""
CONTEXT:
The user is iterating on their CV based on your previous advice.
PREVIOUS ADVICE:
---
{previous_feedback}
---

TASK:
1. **Verification**: Did the user effectively address your previous feedback? Be specific ("You fixed the typo", "You added the missing skill").
2. **New Analysis**: Analyze the new content as described below.

{original_prompt}
"""
    else:
        prompt = original_prompt

    return llm.invoke(prompt).strip()




def process_cv():
    """CV değişikliklerini kontrol et ve analiz et."""
    try:
        if not os.path.exists(PDF_PATH):
            logger.warning("PDF bulunamadı.")
            return
        
        new_hash = file_sha256(PDF_PATH)
        old_hash, old_text = get_last_state()
        
        if new_hash == old_hash:
            return

        new_text = pdf_to_text(PDF_PATH)

        if not old_text:
            # First run or empty DB, just save baseline
            save_analysis(new_hash, "Baseline (First Run)", "Initial setup.", new_text)
            logger.info("Baseline kaydedildi (ilk sürüm).")
            return

        if new_text == old_text:
            return

        diff_text = make_diff(old_text, new_text)

        # Çok büyük diff’i LLM’e yollama (maliyet değil ama hız + kalite)
        if len(diff_text) > 10000:
            diff_text = diff_text[:12000] + "\n... (diff truncated)"

        print("\n" + "="*70)
        logger.info("CV PDF değişikliği tespit edildi.")
        print("="*70)

        # Önceki feedback'i al
        previous_feedback = get_last_feedback()
        if previous_feedback:
            logger.info("Önceki hafıza yüklendi (Memory).")

        result = analyze(diff_text, new_text, previous_feedback)
        print("\nLLM Analizi:\n")
        print(result)

        # Yeni sonucu kaydet
        save_analysis(new_hash, diff_text, result, new_text)

        if ON_ANALYSIS_COMPLETE:
            ON_ANALYSIS_COMPLETE(result)


    except Exception as e:
        logger.error(f"Hata oluştu: {e}", exc_info=True)


class Handler(FileSystemEventHandler):
    def __init__(self):
        self._last_fire = 0.0

    def _handle_change(self, path: str):
        if os.path.abspath(path) != PDF_PATH:
            return

        # hızlı tekrarları engelle
        now = time.time()
        if now - self._last_fire < 1.0:
            return
        self._last_fire = now

        # dosya yazımı bitsin
        time.sleep(0.8)

        process_cv()

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._handle_change(getattr(event, "dest_path", ""))




def main():
    wait_for_ollama()
    init_db()  # DB'yi hazırla

    # Tek seferlik kontrol modunu destekle
    if "--once" in sys.argv:
        logger.info("Tek seferlik analiz modu (--once) aktif.")
        process_cv()
        logger.info("Analiz tamamlandı, çıkılıyor.")
        return

    folder = os.path.dirname(PDF_PATH) or "."
    observer = Observer(timeout=3.0)
    observer.schedule(Handler(), folder, recursive=False)
    observer.start()

    print(f"İzleniyor: {PDF_PATH}")
    print("Çıkış: CTRL+C")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
