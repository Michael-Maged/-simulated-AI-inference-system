#!/bin/bash
# Build all images and deploy to Docker Swarm
# Usage: ./deploy-swarm.sh [registry-prefix]
# Example: ./deploy-swarm.sh myregistry.io/myproject

REGISTRY=${1:-localhost}

echo "=== Building images ==="
docker build -t ${REGISTRY}/worker:latest -f workers/Dockerfile .
docker build -t ${REGISTRY}/master:latest -f master/Dockerfile .
docker build -t ${REGISTRY}/load-balancer:latest -f load_balancer/Dockerfile .
docker build -t ${REGISTRY}/rag-retriever:latest -f rag/Dockerfile .
docker build -t ${REGISTRY}/ingestion:latest -f ingestion/Dockerfile .

# If using a remote registry, push images
if [ "$REGISTRY" != "localhost" ]; then
    echo "=== Pushing images to $REGISTRY ==="
    docker push ${REGISTRY}/worker:latest
    docker push ${REGISTRY}/master:latest
    docker push ${REGISTRY}/load-balancer:latest
    docker push ${REGISTRY}/rag-retriever:latest
    docker push ${REGISTRY}/ingestion:latest
fi

echo "=== Initializing Swarm (skip if already a manager) ==="
docker swarm init 2>/dev/null || echo "Already in swarm mode"

echo "=== Deploying stack ==="
REGISTRY=${REGISTRY} OLLAMA_MODEL=${OLLAMA_MODEL:-tinyllama} \
    docker stack deploy -c docker-stack.yml inference

echo ""
echo "=== Stack deployed ==="
echo "Scale workers:  docker service scale inference_worker=8"
echo "Check status:   docker service ls"
echo "View logs:      docker service logs inference_worker"
echo "Remove stack:   docker stack rm inference"
