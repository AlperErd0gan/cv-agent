#!/bin/bash

# Function to check if Ollama is ready
check_ollama() {
    curl -s -f http://localhost:11434/api/tags > /dev/null
    return $?
}

echo "Checking Ollama status..."

if check_ollama; then
    echo "Ollama is already running."
else
    echo "Ollama is not running. Starting Ollama..."
    # Start Ollama in background and redirect output to avoid clutter
    ollama serve > /dev/null 2>&1 &
    
    # Wait for Ollama to become ready
    echo "Waiting for Ollama to be ready..."
    count=0
    while ! check_ollama; do
        sleep 1
        count=$((count+1))
        if [ $count -ge 10 ]; then
            echo "Timeout waiting for Ollama! Please start it manually."
            exit 1
        fi
    done
    echo "Ollama started successfully!"
fi

echo "Starting CV Agent (Backend + Frontend)..."
# Build containers
docker-compose up --build
