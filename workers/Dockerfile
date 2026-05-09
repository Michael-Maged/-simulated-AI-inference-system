FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

COPY common/ ./common/
RUN python -m grpc_tools.protoc -I./common/protos --python_out=./common/protos --grpc_python_out=./common/protos ./common/protos/worker.proto

COPY workers/ .

CMD ["python", "server.py"]
