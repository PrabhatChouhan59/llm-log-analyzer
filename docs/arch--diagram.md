# Architecture Diagram - LLM DevOps Platform

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster (KIND)                        │
│                         Namespace: devops-platform                       │
│                                                                          │
│  ┌──────────────────┐     HTTP /logs      ┌───────────────────────────┐ │
│  │                  │ ──────────────────► │                           │ │
│  │  log-generator   │                     │      llm-analyzer         │ │
│  │  (Flask :5000)   │                     │      (Flask :8080)        │ │
│  │                  │                     │                           │ │
│  │  Generates:      │                     │  1. Fetches logs          │ │
│  │  - INFO logs     │                     │  2. Builds AI prompt      │ │
│  │  - WARNING logs  │                     │  3. Calls Ollama          │ │
│  │  - ERROR logs    │                     │  4. Parses AI response    │ │
│  │  - CRITICAL logs │                     │  5. Updates /metrics      │ │
│  │                  │                     │     - alert_level         │ │
│  │  /metrics :8000  │                     │     - health_score        │ │
│  └──────────────────┘                     └──────────┬────────────────┘ │
│          │                                           │                  │
│          │ /metrics                                  │ HTTP POST /api/generate
│          ▼                                           ▼                  │
│  ┌──────────────┐                        ┌───────────────────────────┐  │
│  │  Prometheus  │                        │         Ollama            │  │
│  │  (scrapes    │                        │   (AI model server)       │  │
│  │   /metrics)  │                        │   Model: mistral          │  │
│  └──────┬───────┘                        │   Port: 11434             │  │
│         │                                │   Storage: PVC (20GB)     │  │
│         │ PromQL queries                 └───────────────────────────┘  │
│         ▼                                                                │
│  ┌──────────────┐                                                        │
│  │   Grafana    │                                                        │
│  │  Dashboards  │                                                        │
│  └──────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────┘

         ▲ ArgoCD watches Git repo and deploys changes automatically
         │
┌────────┴─────────────────────────────────────────────────────────────┐
│                         GitOps Flow                                   │
│                                                                       │
│  Developer → git push → GitHub → ArgoCD detects → kubectl apply      │
│                                    (every 3 min)                      │
│                                                                       │
│  GitHub Actions CI Pipeline:                                          │
│  Push to main → Lint Python → Build Docker images → Push to Hub      │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Language/Tool | Port | Role |
|-----------|--------------|------|------|
| **log-generator** | Python/Flask | 5000 (API), 8000 (metrics) | Simulates app logs |
| **llm-analyzer** | Python/Flask | 8080 | Analyzes logs with AI |
| **Ollama** | Go binary | 11434 | Runs AI model locally |
| **Prometheus** | Go binary | 9090 | Scrapes & stores metrics |
| **Grafana** | Go binary | 3000 | Visualizes metrics |
| **ArgoCD** | Go binary | 443 | GitOps deployment |

## Kubernetes Resource Map

```
devops-platform namespace:
  Deployments:     log-generator, llm-analyzer, ollama
  Services:        log-generator-service, llm-analyzer-service, ollama-service
  PVC:             ollama-pvc (20Gi - stores AI model files)

monitoring namespace:
  Helm Releases:   prometheus, grafana

argocd namespace:
  ArgoCD Application: llm-devops-platform
```

## How Services Discover Each Other

In Kubernetes, Services get stable DNS names. No hardcoded IPs needed!

```
llm-analyzer → calls → http://ollama-service.devops-platform.svc.cluster.local:11434
llm-analyzer → calls → http://log-generator-service.devops-platform.svc.cluster.local:5000
prometheus   → scrapes → http://log-generator-service.devops-platform.svc.cluster.local:8000/metrics
prometheus   → scrapes → http://llm-analyzer-service.devops-platform.svc.cluster.local:8080/metrics
```
