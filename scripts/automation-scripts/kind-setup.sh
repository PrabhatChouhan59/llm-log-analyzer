#!/bin/bash
# =============================================================================
# setup-kind.sh - Sets up a local Kubernetes cluster using KIND
# =============================================================================
#
# KIND = Kubernetes IN Docker
# It runs a full Kubernetes cluster inside Docker containers on your laptop!
# This is perfect for local development and testing.
#
# Prerequisites:
#   - Docker installed and running
#   - kubectl installed
#   - kind installed: https://kind.sigs.k8s.io/docs/user/quick-start/
#   - helm installed: https://helm.sh/docs/intro/install/
#
# Usage:
#   chmod +x scripts/setup-kind.sh
#   ./scripts/setup-kind.sh
# =============================================================================

set -e  # Exit immediately if any command fails

# ---- Colors for pretty output ----
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"  # No Color (reset)

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

CLUSTER_NAME="llm-devops-platform"

info "========================================"
info "  LLM DevOps Platform - Local Setup"
info "========================================"

# ---- Check prerequisites ----
info "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || error "Docker not found. Install from https://docs.docker.com/get-docker/"
command -v kubectl >/dev/null 2>&1 || error "kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/"
command -v kind    >/dev/null 2>&1 || error "kind not found. Install: go install sigs.k8s.io/kind@latest"
command -v helm    >/dev/null 2>&1 || error "helm not found. Install from https://helm.sh"

info "All prerequisites found!"

# ---- Create KIND cluster ----
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    warning "KIND cluster '${CLUSTER_NAME}' already exists. Skipping creation."
else
    info "Creating KIND cluster '${CLUSTER_NAME}'..."

    cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    # Map host port 80 to container port to allow ingress
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30000
        hostPort: 30000
        protocol: TCP
      - containerPort: 30001
        hostPort: 30001
        protocol: TCP
EOF

    info "KIND cluster created successfully!"
fi

# ---- Set kubectl context to our cluster ----
kubectl cluster-info --context "kind-${CLUSTER_NAME}"
info "kubectl is now pointing to your KIND cluster"

# ---- Create namespace ----
info "Creating devops-platform namespace..."
kubectl apply -f infrastructure/namespace/devops-platform.yaml

# ---- Build Docker images and load into KIND ----
info "Building Docker images..."

info "Building log-generator image..."
docker build -t log-generator:latest services/log-generator/

info "Building llm-analyzer image..."
docker build -t llm-analyzer:latest services/llm-analyzer/

# KIND doesn't pull from Docker Hub by default - we load images directly
info "Loading images into KIND cluster..."
kind load docker-image log-generator:latest --name "${CLUSTER_NAME}"
kind load docker-image llm-analyzer:latest --name "${CLUSTER_NAME}"

info "Docker images loaded into KIND cluster!"

# ---- Install ArgoCD ----
info "Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

info "Waiting for ArgoCD pods to be ready (this takes 2-3 minutes)..."
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

# ---- Get ArgoCD initial password ----
info "Getting ArgoCD admin password..."
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
info "ArgoCD admin password: ${ARGOCD_PASSWORD}"

# ---- Apply infrastructure manifests directly (for initial setup) ----
info "Deploying application manifests..."
kubectl apply -f infrastructure/ollama/pvc.yaml
kubectl apply -f infrastructure/ollama/deployment.yaml
kubectl apply -f infrastructure/ollama/service.yaml
kubectl apply -f infrastructure/log-generator/deployment.yaml
kubectl apply -f infrastructure/log-generator/service.yaml
kubectl apply -f infrastructure/llm-analyzer/deployment.yaml
kubectl apply -f infrastructure/llm-analyzer/service.yaml

info "Waiting for Ollama pod to be ready (this downloads the AI model - ~5 min)..."
kubectl wait --for=condition=ready pod -l app=ollama -n devops-platform --timeout=600s || warning "Ollama not ready yet - it may still be downloading the model"

# ---- Setup port forwarding (access services locally) ----
info "========================================"
info "  Setup Complete! Access your services:"
info "========================================"
info ""
info "  Run these in separate terminals to access services:"
info ""
info "  Log Generator API:"
info "    kubectl port-forward svc/log-generator-service 5000:5000 -n devops-platform"
info "    Then open: http://localhost:5000/logs"
info ""
info "  LLM Analyzer API:"
info "    kubectl port-forward svc/llm-analyzer-service 8080:8080 -n devops-platform"
info "    Then open: http://localhost:8080/analysis"
info ""
info "  ArgoCD UI:"
info "    kubectl port-forward svc/argocd-server 8888:443 -n argocd"
info "    Then open: https://localhost:8888"
info "    Username: admin | Password: ${ARGOCD_PASSWORD}"
info ""
info "  Next step: Run ./scripts/deploy-monitoring.sh"
