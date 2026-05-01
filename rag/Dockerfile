FROM inference-base:latest
WORKDIR /app
COPY rag/requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt
COPY rag/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
