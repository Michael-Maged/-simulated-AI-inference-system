import os
import sys
import grpc
from concurrent import futures

sys.path.insert(0, "/app")
from common.protos import worker_pb2, worker_pb2_grpc


class WorkerServicer(worker_pb2_grpc.WorkerServicer):
    def Infer(self, request, context):
        return worker_pb2.InferResponse(
            request_id=request.request_id,
            response="stub response",
            latency_ms=0.0,
            rag_used=False,
            worker_id=os.getenv("WORKER_ID", "unknown"),
        )

    def Health(self, request, context):
        return worker_pb2.HealthResponse(ready=True)


def serve():
    port = os.getenv("GRPC_PORT", "9001")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    worker_pb2_grpc.add_WorkerServicer_to_server(WorkerServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Worker gRPC server started on port {port}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
