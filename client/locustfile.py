import random
from locust import HttpUser, task, between, constant_throughput

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
]


class NormalUser(HttpUser):
    wait_time = between(0.1, 1.0)
    weight = 3

    @task
    def infer(self):
        self.client.post(
            "/infer",
            json={"prompt": random.choice(PROMPTS), "max_tokens": 128, "priority": "normal"},
            name="/infer [normal]",
        )


class HeavyUser(HttpUser):
    wait_time = constant_throughput(0.5)
    weight = 1

    @task
    def infer_heavy(self):
        prompt = f"Please provide a detailed explanation of: {random.choice(PROMPTS)}"
        self.client.post(
            "/infer",
            json={"prompt": prompt, "max_tokens": 256, "priority": "high"},
            name="/infer [heavy]",
        )
