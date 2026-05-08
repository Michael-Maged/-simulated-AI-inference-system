import random
import time
import threading
from locust import HttpUser, task, between, events

PROMPTS = [
    "What is a circuit breaker in distributed systems?",
    "Explain load balancing algorithms.",
    "What is RAG in the context of AI?",
    "How does Redis work as a message queue?",
    "What is gRPC and how does it differ from REST?",
    "Explain the CAP theorem.",
    "What is a vector database used for?",
    "How does Prometheus collect metrics?",
    "What is the purpose of Docker Compose?",
    "Explain p95 latency and why it matters.",
    "What is semantic caching in AI systems?",
    "How do heartbeat mechanisms work in distributed systems?",
    "What is fault tolerance and how is it achieved?",
    "Explain the difference between throughput and latency.",
    "What is the PagedAttention technique used in vLLM?",
    "How does consistent hashing work?",
    "What is the two-phase commit protocol?",
    "Explain the Raft consensus algorithm.",
    "What is a service mesh in microservices?",
    "How does exponential backoff work in retries?",
    "What is the difference between horizontal and vertical scaling?",
    "Explain eventual consistency in distributed databases.",
    "What is a Bloom filter and when is it useful?",
    "How does a distributed hash table work?",
    "What is backpressure in streaming systems?",
    "Explain the saga pattern for distributed transactions.",
    "What is a sidecar proxy in Kubernetes?",
    "How does leader election work in distributed systems?",
    "What is the thundering herd problem?",
    "Explain zero-copy networking.",
    "What is QUIC and how does it improve on TCP?",
    "How does token bucket rate limiting work?",
    "What is a write-ahead log in databases?",
    "Explain the actor model of concurrency.",
    "What is cooperative vs preemptive multitasking?",
    "How does columnar storage improve query performance?",
    "What is a materialized view in databases?",
    "Explain the difference between OLTP and OLAP.",
    "What is connection pooling and why does it matter?",
    "How does a time-series database store data efficiently?",
    "What is idempotency and why is it important in APIs?",
    "Explain optimistic vs pessimistic locking.",
    "What is long-polling vs WebSocket?",
    "How does the gossip protocol spread information?",
    "What is a cold start problem in serverless computing?",
    "Explain the difference between a queue and a topic in messaging.",
    "What is a fanout pattern in distributed systems?",
    "How does distributed tracing work?",
    "What is the strangler fig pattern in microservices?",
    "Explain canary deployments and blue-green deployments.",
]

REQUEST_TIMEOUT = 180  # seconds — must match server-side timeouts

# Track in-flight requests: {key: start_time}
_in_flight = {}
_lock = threading.Lock()


@events.quitting.add_listener
def mark_abandoned_as_failed(environment, **kwargs):
    """
    When the test ends, any still-pending request gets the full REQUEST_TIMEOUT
    as its response time before being marked failed. This correctly represents
    that the request was abandoned mid-wait, not that it instantly failed.
    """
    with _lock:
        abandoned = dict(_in_flight)

    if not abandoned:
        return

    print(f"\n[locust] {len(abandoned)} requests still in-flight when test ended — marking as failed with {REQUEST_TIMEOUT}s response time")

    for key, start in abandoned.items():
        elapsed_ms = (time.time() - start) * 1000
        # Use the full timeout as response time if request hasn't hit it yet,
        # otherwise use actual elapsed time (request was already past deadline)
        reported_ms = max(elapsed_ms, REQUEST_TIMEOUT * 1000)
        environment.events.request.fire(
            request_type="POST",
            name="/infer [abandoned]",
            response_time=reported_ms,
            response_length=0,
            exception=Exception(f"Request abandoned after {reported_ms/1000:.1f}s — test ended before completion"),
            context={},
        )


class InferenceUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def infer(self):
        key = f"{id(self)}-{time.monotonic()}"
        start = time.time()

        with _lock:
            _in_flight[key] = start

        try:
            self.client.post(
                "/infer",
                json={"prompt": random.choice(PROMPTS), "max_tokens": 10, "priority": "normal"},
                name="/infer",
                timeout=REQUEST_TIMEOUT,
            )
        finally:
            with _lock:
                _in_flight.pop(key, None)
