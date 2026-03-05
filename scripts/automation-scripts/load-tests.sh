#!/bin/bash
# =============================================================================
# load-test.sh - Simulates traffic to trigger varied log patterns
# =============================================================================
# This script hits the log-generator API to verify it's working and
# triggers the LLM analyzer to run an analysis manually.
#
# Usage:
#   chmod +x scripts/load-test.sh
#   ./scripts/load-test.sh
# =============================================================================

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

LOG_GEN_URL="${LOG_GEN_URL:-http://localhost:5000}"
ANALYZER_URL="${ANALYZER_URL:-http://localhost:8080}"

info "========================================"
info "  LLM DevOps Platform - Load Test"
info "========================================"
info "Log Generator: ${LOG_GEN_URL}"
info "LLM Analyzer:  ${ANALYZER_URL}"
info ""

# Check health of log-generator
info "Checking log-generator health..."
if curl -sf "${LOG_GEN_URL}/health" > /dev/null; then
    info "✅ Log Generator is healthy!"
else
    warn "❌ Log Generator not reachable at ${LOG_GEN_URL}"
    warn "   Run: kubectl port-forward svc/log-generator-service 5000:5000 -n devops-platform"
    exit 1
fi

# Check health of llm-analyzer
info "Checking llm-analyzer health..."
if curl -sf "${ANALYZER_URL}/health" > /dev/null; then
    info "✅ LLM Analyzer is healthy!"
else
    warn "❌ LLM Analyzer not reachable at ${ANALYZER_URL}"
    warn "   Run: kubectl port-forward svc/llm-analyzer-service 8080:8080 -n devops-platform"
fi

# Fetch and display some logs
info ""
info "Fetching recent logs from log-generator..."
echo ""
curl -s "${LOG_GEN_URL}/logs/summary" | python3 -m json.tool
echo ""

# Show last 5 logs
info "Last 5 log entries:"
curl -s "${LOG_GEN_URL}/logs" | python3 -c "
import json, sys
data = json.load(sys.stdin)
logs = data.get('logs', [])[-5:]
for log in logs:
    print(f\"[{log['timestamp'][:19]}] {log['level']:<8} {log['message']}\")
"
echo ""

# Trigger a manual analysis
info "Triggering manual LLM analysis..."
RESPONSE=$(curl -sf -X POST "${ANALYZER_URL}/analysis/trigger" 2>/dev/null || echo "{}")
echo "${RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${RESPONSE}"

info ""
info "Waiting 35 seconds for analysis to complete..."
sleep 35

# Fetch analysis result
info "Fetching analysis result..."
echo ""
curl -s "${ANALYZER_URL}/analysis" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Status:      {data.get('status', 'unknown')}\")
print(f\"Alert Level: {data.get('alert_level', 'UNKNOWN')}\")
print(f\"Logs Analyzed: {data.get('logs_analyzed', 0)}\")
print(f\"Duration: {data.get('duration_seconds', '?')}s\")
print()
print('--- AI Analysis ---')
print(data.get('result', 'No result yet'))
"

info ""
info "Load test complete!"
