import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Create dummy test files if they don't exist to satisfy any immediate checks,
# though mocks should handle most things.
# We set these ENV vars BEFORE importing main/watcher so they pick up local paths
# instead of /data/ which might not exist or be writable on host.
os.environ["DB_PATH"] = "./test.db"
os.environ["PDF_PATH"] = "./test.pdf"

# Add the parent directory to sys.path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "CV Agent Backend Running"}

@patch("sqlite3.connect")
def test_get_history(mock_connect):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall return value
    mock_cursor.fetchall.return_value = [
        (1, "Test content", "Test feedback", "2023-01-01")
    ]
    
    response = client.get("/history")
    
    assert response.status_code == 200
    assert response.json() == {
        "history": [[1, "Test content", "Test feedback", "2023-01-01"]]
    }
    
    # Verify DB interactions
    mock_connect.assert_called_once()
    mock_cursor.execute.assert_called_once()
    mock_cursor.fetchall.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("builtins.open", new_callable=MagicMock)
@patch("os.path.dirname")
def test_upload_cv(mock_dirname, mock_open):
    # Setup mocks
    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file
    
    # Create a dummy PDF content
    pdf_content = b"%PDF-1.4 test pdf content"
    
    response = client.post(
        "/upload",
        files={"file": ("cv.pdf", pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    assert response.json() == {
        "status": "success", 
        "message": "CV uploaded and analysis triggered."
    }
    
    # Verify file was written
    mock_open.assert_called_once()
    mock_file.write.assert_called_with(pdf_content)

@patch("main.get_last_state")
@patch("main.chat_with_cv")
def test_chat_endpoint(mock_chat_with_cv, mock_get_last_state):
    # Mock state to return some text
    mock_get_last_state.return_value = (123, "Extracted CV Text")
    
    # Mock chat response
    mock_chat_with_cv.return_value = "This is a response from the LLM."
    
    response = client.post(
        "/chat",
        json={"message": "Hello AI"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"response": "This is a response from the LLM."}
    
    # Verify mocks called correctly
    mock_get_last_state.assert_called_once()
    mock_chat_with_cv.assert_called_with("Hello AI", "Extracted CV Text")

@patch("main.get_last_state")
def test_chat_endpoint_no_cv(mock_get_last_state):
    # Mock state to return no text (CV not processed yet)
    mock_get_last_state.return_value = (None, None)
    
    response = client.post(
        "/chat",
        json={"message": "Hello AI"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"response": "CV henüz yüklenmedi veya analiz edilmedi."}
