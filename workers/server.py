import os
import sys
import asyncio
import logging
import threading
import time

import grpc
import httpx
from concurrent import futures
from prometheus_client import start_http_server, Counter, Histogram

sys.path.insert(0, "/app")
from common.protos import worker_pb2, worker_pb2_grpc
from workers.inference import run_inference

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

WORKER_ID = os.getenv("WORKER_ID", "worker-unknown")
GRPC_PORT = os.getenv("GRPC_PORT", "9001")
MASTER_URL = os.getenv("MASTER_URL", "http://localhost:8001")

INFER_REQUESTS = Counter("worker_infer_requests_total", "Total inference requests", ["worker_id"])
INFER_LATENCY = Histogram("worker_infer_latency_seconds", "Inference latency", ["worker_id"],
                          buckets=[0.1, 0.5, 1, 2, 5, 10, 30])
INFER_ERRORS = Counter("worker_infer_errors_total", "Inference errors", ["worker_id"])

_in_flight = 0


class WorkerServicer(worker_pb2_grpc.WorkerServicer):
    def Infer(self, request, context):
        global _in_flight
        _in_flight += 1
        INFER_REQUESTS.labels(worker_id=WORKER_ID).inc()
        try:
            loop = asyncio.new_event_loop()
            response_text, latency_ms = loop.run_until_complete(
                run_inference(request.prompt, request.max_tokens)
            )
            loop.close()
            INFER_LATENCY.labels(worker_id=WORKER_ID).observe(latency_ms / 1000)
            log.info(f"{WORKER_ID} completed {request.request_id} in {latency_ms:.0f}ms")
            return worker_pb2.InferResponse(
                request_id=request.request_id,
                response=response_text,
                latency_ms=latency_ms,
                rag_used=True,
                worker_id=WORKER_ID,
            )
        except Exception as e:
            INFER_ERRORS.labels(worker_id=WORKER_ID).inc()
            log.error(f"{WORKER_ID} inference error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return worker_pb2.InferResponse()
        finally:
            _in_flight -= 1

    def Health(self, request, context):
        return worker_pb2.HealthResponse(ready=True)


def _send_heartbeat():
    def _loop():
        while True:
            try:
                httpx.post(
                    f"{MASTER_URL}/heartbeat",
                    json={"worker_id": WORKER_ID, "queue_depth": _in_flight, "last_latency_ms": 0.0},
                    timeout=3.0,
                )
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=_loop, daemon=True).start()


def serve():
    start_http_server(8080)
    _send_heartbeat()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    worker_pb2_grpc.add_WorkerServicer_to_server(WorkerServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    log.info(f"{WORKER_ID} gRPC server started on port {GRPC_PORT}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
