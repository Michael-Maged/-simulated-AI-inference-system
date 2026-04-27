FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl zstd && \
    curl -fsSL https://ollama.ai/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*
COPY workers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY workers/ .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
