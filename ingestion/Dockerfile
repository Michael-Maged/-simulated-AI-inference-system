FROM inference-base:latest
WORKDIR /app
COPY ingestion/requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt
COPY ingestion/ .
