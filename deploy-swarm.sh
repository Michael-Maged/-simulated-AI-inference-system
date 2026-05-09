#!/bin/bash
# Multi-node Docker Swarm deployment with GPU support
#
# QUICK START (run on manager laptop):
#   ./deploy-swarm.sh setup-registry    # start local registry on port 5000
#   ./deploy-swarm.sh init              # init swarm, print join token
#   ./deploy-swarm.sh build-push        # build images + push to local registry
#   ./deploy-swarm.sh label-gpu <node>  # label a node as GPU-capable
#   ./deploy-swarm.sh deploy            # deploy the full stack
#
# On each WORKER laptop (after running init above):
#   docker swarm join --token <TOKEN> <MANAGER_IP>:2377
#
# Then back on manager, label it:
#   ./deploy-swarm.sh label-gpu <worker-node-id>
#
# Scale workers later:
#   docker service scale inference_worker=16

set -e

MANAGER_IP=$(hostname -I | awk '{print $1}')
REGISTRY="${REGISTRY:-${MANAGER_IP}:5000}"
OLLAMA_MODEL="${OLLAMA_MODEL:-tinyllama}"
WORKER_REPLICAS="${WORKER_REPLICAS:-4}"
STACK_NAME="inference"

# ── Helpers ───────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  setup-registry    Start local Docker registry on port 5000"
    echo "  init              Init swarm and print join token for workers"
    echo "  build-push        Build all images and push to registry"
    echo "  label-gpu <node>  Label a node as GPU-capable (node ID or hostname)"
    echo "  deploy            Deploy the full stack"
    echo "  status            Show running services"
    echo "  scale <n>         Scale workers to n replicas"
    echo "  pull-model        Pull Ollama model on all GPU nodes"
    echo "  teardown          Remove the stack"
    echo ""
    echo "Environment:"
    echo "  REGISTRY          Image registry prefix (default: ${MANAGER_IP}:5000)"
    echo "  OLLAMA_MODEL      Model to use (default: tinyllama)"
    echo "  WORKER_REPLICAS   Initial worker count (default: 4)"
}

require_swarm_manager() {
    if ! docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null | grep -q true; then
        echo "ERROR: Not a swarm manager. Run './deploy-swarm.sh init' first."
        exit 1
    fi
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_setup_registry() {
    echo "=== Starting local registry on ${MANAGER_IP}:5000 ==="
    if docker ps --format '{{.Names}}' | grep -q '^registry$'; then
        echo "Registry already running."
    else
        docker run -d \
            --name registry \
            --restart always \
            -p 5000:5000 \
            -v registry-data:/var/lib/registry \
            registry:2
        echo "Registry started."
    fi

    echo ""
    echo ">>> On EVERY worker laptop, add this to /etc/docker/daemon.json:"
    echo "    { \"insecure-registries\": [\"${MANAGER_IP}:5000\"] }"
    echo "    Then: sudo systemctl restart docker"
    echo ""
    echo ">>> On THIS manager, if not already present, also add the insecure registry"
    echo "    entry and restart Docker before building/pushing images."
}

cmd_init() {
    echo "=== Initialising Docker Swarm ==="
    if docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q active; then
        echo "Already in swarm mode."
    else
        docker swarm init --advertise-addr "${MANAGER_IP}"
    fi

    echo ""
    echo "=== Worker join command (run this on each GPU laptop) ==="
    docker swarm join-token worker
    echo ""
    echo "After each worker joins, label GPU nodes:"
    echo "  ./deploy-swarm.sh label-gpu <node-id>"
    echo ""
    echo "List nodes with:  docker node ls"
}

cmd_build_push() {
    echo "=== Building and pushing images to ${REGISTRY} ==="
    images=(
        "worker:workers/Dockerfile"
        "master:master/Dockerfile"
        "load-balancer:load_balancer/Dockerfile"
        "rag-retriever:rag/Dockerfile"
        "ingestion:ingestion/Dockerfile"
    )
    for entry in "${images[@]}"; do
        name="${entry%%:*}"
        dockerfile="${entry##*:}"
        echo "--- Building ${REGISTRY}/${name}:latest ---"
        docker build -t "${REGISTRY}/${name}:latest" -f "${dockerfile}" .
        docker push "${REGISTRY}/${name}:latest"
    done
    echo "All images pushed to ${REGISTRY}."
}

cmd_label_gpu() {
    local node="$1"
    if [ -z "$node" ]; then
        echo "ERROR: provide node ID or hostname"
        echo "  docker node ls   ← shows node IDs"
        exit 1
    fi
    require_swarm_manager
    docker node update --label-add gpu=true "$node"
    echo "Node '$node' labelled gpu=true. Ollama will be scheduled here."
}

cmd_deploy() {
    require_swarm_manager

    gpu_nodes=$(docker node ls --filter "node.label=gpu=true" --format "{{.ID}}" 2>/dev/null | wc -l)
    if [ "$gpu_nodes" -eq 0 ]; then
        echo "WARNING: No nodes labelled gpu=true. Ollama won't start anywhere."
        echo "  Run: ./deploy-swarm.sh label-gpu <node-id>"
        read -r -p "Continue anyway? [y/N] " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
    else
        echo "Found ${gpu_nodes} GPU node(s). Ollama will run on each."
    fi

    echo "=== Deploying stack '${STACK_NAME}' ==="
    REGISTRY="${REGISTRY}" \
    OLLAMA_MODEL="${OLLAMA_MODEL}" \
    WORKER_REPLICAS="${WORKER_REPLICAS}" \
        docker stack deploy \
            --with-registry-auth \
            -c docker-stack.yml \
            "${STACK_NAME}"

    echo ""
    echo "=== Stack deployed. Monitor with: ==="
    echo "  docker service ls"
    echo "  docker service logs ${STACK_NAME}_worker -f"
    echo ""
    echo "  Pull Ollama model on GPU nodes: ./deploy-swarm.sh pull-model"
}

cmd_status() {
    require_swarm_manager
    echo "=== Nodes ==="
    docker node ls
    echo ""
    echo "=== Services ==="
    docker service ls
}

cmd_scale() {
    local n="$1"
    if [ -z "$n" ]; then echo "Usage: $0 scale <n>"; exit 1; fi
    require_swarm_manager
    docker service scale "${STACK_NAME}_worker=${n}"
    echo "Workers scaled to ${n}."
}

cmd_pull_model() {
    require_swarm_manager
    echo "=== Pulling model '${OLLAMA_MODEL}' on all Ollama instances ==="
    # Get all Ollama task IPs via overlay network task DNS
    # Simpler: exec into any running ollama task
    local ollama_task
    ollama_task=$(docker service ps "${STACK_NAME}_ollama" --filter "desired-state=running" --format "{{.ID}}" | head -1)
    if [ -z "$ollama_task" ]; then
        echo "No running Ollama tasks found. Is the stack deployed with GPU nodes?"
        exit 1
    fi
    # Pull model in one Ollama; others share the named volume ollama-models
    docker exec "$(docker ps -q -f name="${STACK_NAME}_ollama")" \
        ollama pull "${OLLAMA_MODEL}" || \
    echo "Could not exec directly. SSH into a GPU node and run: docker exec <ollama-container> ollama pull ${OLLAMA_MODEL}"
}

cmd_teardown() {
    require_swarm_manager
    echo "Removing stack '${STACK_NAME}'..."
    docker stack rm "${STACK_NAME}"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "${1:-}" in
    setup-registry) cmd_setup_registry ;;
    init)           cmd_init ;;
    build-push)     cmd_build_push ;;
    label-gpu)      cmd_label_gpu "$2" ;;
    deploy)         cmd_deploy ;;
    status)         cmd_status ;;
    scale)          cmd_scale "$2" ;;
    pull-model)     cmd_pull_model ;;
    teardown)       cmd_teardown ;;
    *)              usage ;;
esac
