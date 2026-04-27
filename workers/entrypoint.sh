#!/bin/bash
set -e

ollama serve &

echo "Waiting for Ollama..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done
echo "Ollama ready. Pulling model ${OLLAMA_MODEL:-phi3:mini}..."

ollama pull "${OLLAMA_MODEL:-phi3:mini}"
echo "Model ready. Starting gRPC server..."

exec python server.py
