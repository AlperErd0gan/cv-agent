#!/bin/bash

check_ollama() {
    curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1
}

echo "Checking Ollama status..."

if ! check_ollama; then
    echo "Ollama is not running. Starting Ollama..."

    if [[ "$(uname)" == "Darwin" ]]; then
        open -a Ollama 2>/dev/null || ollama serve > /dev/null 2>&1 &
    else
        ollama serve > /dev/null 2>&1 &
    fi

    echo "Waiting for Ollama to be ready..."
    count=0
    while ! check_ollama; do
        sleep 1
        count=$((count+1))
        if [ $count -ge 30 ]; then
            echo ""
            echo "ERROR: Ollama did not start within 30 seconds."
            echo "  macOS : Launch the Ollama app from your Applications folder."
            echo "  Linux : Run 'ollama serve' in a separate terminal."
            exit 1
        fi
        printf "."
    done
    echo ""
    echo "Ollama started successfully."
else
    echo "Ollama is already running."
fi

echo "Starting CV Agent (Backend + Frontend)..."
docker-compose up --build
