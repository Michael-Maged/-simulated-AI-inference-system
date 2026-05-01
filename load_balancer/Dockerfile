FROM inference-base:latest
WORKDIR /app
COPY load_balancer/requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt
COPY common/ ./common/
COPY load_balancer/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
