#!/bin/bash
# =============================================================================
# deploy-monitoring.sh - Installs Prometheus & Grafana using Helm
# =============================================================================
# Helm is the "package manager for Kubernetes" - like apt/brew but for k8s.
# It installs pre-configured applications called "charts".
#
# Usage:
#   chmod +x scripts/deploy-monitoring.sh
#   ./scripts/deploy-monitoring.sh
# =============================================================================

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }

info "========================================"
info " Deploying Prometheus + Grafana"
info "========================================"

# ---- Add Helm repositories ----
info "Adding Prometheus Helm repository..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

info "Helm repositories updated!"

# ---- Install Prometheus ----
info "Installing Prometheus with custom values..."
helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --create-namespace \
  --values infrastructure/monitoring/prometheus-values.yaml \
  --wait \
  --timeout=5m

info "Prometheus installed successfully!"

# ---- Install Grafana ----
info "Installing Grafana..."
helm upgrade --install grafana grafana/grafana \
  --namespace monitoring \
  --set adminPassword=admin123 \
  --set service.type=ClusterIP \
  --set persistence.enabled=true \
  --set persistence.size=1Gi \
  --wait \
  --timeout=3m

info "Grafana installed successfully!"

# ---- Import our custom dashboard ----
info "The Grafana dashboard can be imported manually:"
info "  1. kubectl port-forward svc/grafana 3000:80 -n monitoring"
info "  2. Open http://localhost:3000 (admin / admin123)"
info "  3. Go to Dashboards → Import"
info "  4. Paste contents of infrastructure/monitoring/grafana-dashboard.json"
info ""

# ---- Configure Grafana data source ----
info "Grafana datasource: Add Prometheus at:"
info "  URL: http://prometheus-server.monitoring.svc.cluster.local"

info "========================================"
info " Monitoring Deployed!"
info "========================================"
info ""
info "Access Grafana:"
info "  kubectl port-forward svc/grafana 3000:80 -n monitoring"
info "  Open: http://localhost:3000"
info "  Username: admin"
info "  Password: admin123"
info ""
info "Access Prometheus:"
info "  kubectl port-forward svc/prometheus-server 9090:80 -n monitoring"
info "  Open: http://localhost:9090"
