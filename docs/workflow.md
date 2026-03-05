# Workflow Guide - Step by Step

## Complete Workflow: From Code to Running Platform

### Step 1: Developer Writes Code
- Edits Python files in `services/log-generator/` or `services/llm-analyzer/`
- Commits and pushes to GitHub

### Step 2: GitHub Actions CI Pipeline Runs Automatically
```
git push origin main
    ↓
GitHub Actions triggers ci-pipeline.yml
    ↓
1. Lint Python code with flake8
2. Build Docker image for log-generator
3. Build Docker image for llm-analyzer
4. Push both images to Docker Hub with :latest tag
```

### Step 3: ArgoCD Detects Changes (GitOps)
- ArgoCD watches the `gitops/` folder in your GitHub repo every 3 minutes
- If Kubernetes YAML files changed → ArgoCD applies them to the cluster
- ArgoCD shows sync status in its web UI

### Step 4: Log Generator Runs
```
log-generator pod starts
    ↓
Background thread generates log entries every 2-5 seconds
    ↓
Logs stored in memory (up to 500 entries)
    ↓
Flask API serves logs at GET /logs
    ↓
Prometheus metrics updated at /metrics:8000
```

### Step 5: LLM Analyzer Analyzes Logs
```
Every 60 seconds (configurable):
    ↓
LogCollector.fetch_logs() → GET http://log-generator-service:5000/logs
    ↓
PromptBuilder.build_analysis_prompt() → formats logs into AI prompt
    ↓
OllamaClient.generate() → POST http://ollama-service:11434/api/generate
    ↓
AI returns analysis with HEALTH STATUS, ISSUES, RECOMMENDATIONS
    ↓
Result stored in-memory, exposed at GET /analysis
    ↓
Prometheus metrics updated: health_score, alert_level, analysis_duration
```

### Step 6: Prometheus Scrapes Metrics
```
Every 15 seconds:
    ↓
Prometheus scrapes /metrics from log-generator (port 8000)
Prometheus scrapes /metrics from llm-analyzer (port 8080)
    ↓
Stores time-series data (15 days retention)
```

### Step 7: Grafana Visualizes Everything
```
Grafana queries Prometheus continuously
    ↓
Dashboard shows:
- System Alert Level (GREEN/YELLOW/RED)
- Health Score gauge (0-100)
- Log counts by level over time
- Memory/CPU trends
- Error rate
- LLM analysis duration
```

## Key URLs (after port-forwarding)

| Service | Command | URL |
|---------|---------|-----|
| Log Generator API | `kubectl port-forward svc/log-generator-service 5000:5000 -n devops-platform` | http://localhost:5000/logs |
| LLM Analyzer API | `kubectl port-forward svc/llm-analyzer-service 8080:8080 -n devops-platform` | http://localhost:8080/analysis |
| ArgoCD UI | `kubectl port-forward svc/argocd-server 8888:443 -n argocd` | https://localhost:8888 |
| Prometheus | `kubectl port-forward svc/prometheus-server 9090:80 -n monitoring` | http://localhost:9090 |
| Grafana | `kubectl port-forward svc/grafana 3000:80 -n monitoring` | http://localhost:3000 |

## Manual Analysis Trigger
```bash
# Trigger an immediate LLM analysis (don't wait 60 seconds)
curl -X POST http://localhost:8080/analysis/trigger

# View the result after ~30 seconds
curl http://localhost:8080/analysis | python3 -m json.tool
```
