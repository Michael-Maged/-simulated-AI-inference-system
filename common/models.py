from pydantic import BaseModel, Field


class InferRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4096)
    max_tokens: int = Field(default=512, ge=1, le=2048)
    priority: str = Field(default="normal", pattern="^(normal|high)$")


class InferResponse(BaseModel):
    request_id: str
    response: str
    latency_ms: float
    cached: bool = False
    worker_id: str = ""


class HeartbeatRequest(BaseModel):
    worker_id: str
    queue_depth: int = 0
    last_latency_ms: float = 0.0
    host: str = ""
    port: int = 9001


class DispatchRequest(BaseModel):
    request_id: str
    prompt: str
    max_tokens: int = 512
    priority: str = "normal"


class RegisterRequest(BaseModel):
    worker_id: str
    host: str
    port: int


class WorkerStatus(BaseModel):
    worker_id: str
    alive: bool
    circuit_state: str
    queue_depth: int
    last_latency_ms: float
