import random
import uuid
from locust import HttpUser, task, between, constant_throughput

# Large prompt pool so cache saturates slowly
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
    "What is a long-polling vs WebSocket connection?",
    "How does the gossip protocol spread information?",
    "What is a cold start problem in serverless computing?",
    "Explain the difference between a queue and a topic in messaging.",
    "What is a fanout pattern in distributed systems?",
    "How does distributed tracing work?",
    "What is the strangler fig pattern in microservices?",
    "Explain canary deployments and blue-green deployments.",
]

TOPICS = [
    "load shedding", "request hedging", "tail latency", "cache stampede",
    "split-brain problem", "network partitions", "quorum reads", "vector clocks",
    "lamport timestamps", "CRDT data structures", "event sourcing", "CQRS pattern",
    "bulkhead pattern", "timeout budget", "deadline propagation", "service discovery",
    "health check endpoints", "graceful degradation", "chaos engineering",
    "capacity planning", "SLO vs SLA", "error budget", "toil in SRE",
]


class NormalUser(HttpUser):
    """Simulates typical users picking from the shared prompt pool — will hit cache after warmup."""
    wait_time = between(0.1, 1.0)
    weight = 5

    @task
    def infer(self):
        self.client.post(
            "/infer",
            json={"prompt": random.choice(PROMPTS), "max_tokens": 50, "priority": "normal"},
            name="/infer [normal]",
            timeout=120,
        )


class HeavyUser(HttpUser):
    """Sends longer requests at high frequency."""
    wait_time = constant_throughput(0.5)
    weight = 2

    @task
    def infer_heavy(self):
        prompt = f"Please provide a detailed explanation of: {random.choice(PROMPTS)}"
        self.client.post(
            "/infer",
            json={"prompt": prompt, "max_tokens": 50, "priority": "high"},
            name="/infer [heavy]",
            timeout=120,
        )


class UniqueUser(HttpUser):
    """Generates unique prompts every request — always bypasses cache, keeps workers busy."""
    wait_time = between(0.5, 2.0)
    weight = 3

    @task
    def infer_unique(self):
        topic = random.choice(TOPICS)
        uid = uuid.uuid4().hex[:6]
        prompt = f"[{uid}] Explain {topic} in distributed systems with a concrete example."
        self.client.post(
            "/infer",
            json={"prompt": prompt, "max_tokens": 50, "priority": "normal"},
            name="/infer [unique]",
            timeout=120,
        )
