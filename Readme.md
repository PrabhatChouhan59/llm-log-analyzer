# 🤖 LLM DevOps Platform

> An AI-powered log analysis platform that uses a local LLM (Mistral via Ollama) to automatically analyze application logs and surface insights through a monitoring dashboard — all running in Kubernetes.

## 🏗️ What This Project Does

```
App Logs → LLM Analysis → Prometheus Metrics → Grafana Dashboard
```

1. **log-generator** simulates a real application producing INFO, WARNING, ERROR, and CRITICAL logs
2. **llm-analyzer** fetches those logs every 60 seconds and asks an AI model: *"What's wrong and what should we do?"*
3. **Ollama** runs the Mistral AI model locally (no OpenAI key needed!)
4. **Prometheus** scrapes metrics from both services
5. **Grafana** displays live dashboards with health scores and alert levels
6. **ArgoCD** manages all deployments via GitOps (just push to Git to deploy)

## 📁 Project Structure

```
llm-devops-platform/
├── services/              # Application code
│   ├── log-generator/     # Simulates logs (Flask + Prometheus metrics)
│   └── llm-analyzer/      # AI analysis pipeline (Flask + Ollama client)
├── k8s-manifests/        # Kubernetes YAML manifests
│   ├── namespace/
│   ├── log-generator/
│   ├── llm-analyzer/
│   ├── ollama/
│   └── monitoring/        # Prometheus config + Grafana dashboard
├── gitops/                # ArgoCD watches this folder
├── scripts/               # Helper scripts  
├── .github/workflows/     # GitHub Actions CI pipeline
└── docs/                  # Architecture diagrams and workflow guide
```

## 🚀 Quick Start

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Docker | Container runtime | [docs.docker.com](https://docs.docker.com/get-docker/) |
| kubectl | Kubernetes CLI | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| kind | Local Kubernetes cluster | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/) |
| helm | Package manager for Kubernetes | [helm.sh](https://helm.sh/docs/intro/install/) |

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_USERNAME/llm-devops-platform.git
cd llm-devops-platform

# Create the KIND cluster, build images, install ArgoCD
chmod +x scripts/*.sh
./scripts/setup-kind.sh
```

### 2. Install Monitoring

```bash
./scripts/deploy-monitoring.sh
```

### 3. Access Your Services

Open four terminals and run:

```bash
# Terminal 1: Log Generator API
kubectl port-forward svc/log-generator-service 5000:5000 -n devops-platform

# Terminal 2: LLM Analyzer API
kubectl port-forward svc/llm-analyzer-service 8080:8080 -n devops-platform

# Terminal 3: Grafana Dashboard
kubectl port-forward svc/grafana 3000:80 -n monitoring

# Terminal 4: ArgoCD UI (optional)
kubectl port-forward svc/argocd-server 8888:443 -n argocd
```

Then open:
- 📊 **Grafana**: http://localhost:3000 (admin / admin123)
- 🔍 **Log API**: http://localhost:5000/logs
- 🤖 **AI Analysis**: http://localhost:8080/analysis

### 4. Run Load Test

```bash
./scripts/load-test.sh
```

## 🔧 How It Works (Beginner Friendly)

### Log Generator (`services/log-generator/`)

| File | What it does |
|------|-------------|
| `app.py` | Flask web server. Background thread generates fake logs every 2-5 seconds. Exposes `GET /logs` endpoint. |
| `metrics.py` | Creates Prometheus metrics (counters, gauges, histograms). Exposed at `:8000/metrics`. |

### LLM Analyzer (`services/llm-analyzer/`)

| File | What it does |
|------|-------------|
| `log_collector.py` | Makes HTTP request to log-generator's `/logs` API. |
| `prompt_builder.py` | Takes raw logs, builds a structured prompt for the AI with statistics and log samples. |
| `ollama_client.py` | Sends the prompt to Ollama's API. Handles retries and timeouts. |
| `analyzer.py` | Orchestrates everything. Runs every 60 seconds. Exposes results at `/analysis`. |

### Infrastructure (`infrastructure/`)

- **Namespace**: Logical grouping of all resources
- **Deployments**: Tell Kubernetes what Docker image to run and how many replicas
- **Services**: Give pods a stable network address (DNS name)
- **PVC**: Persistent storage for Ollama's downloaded model files

### GitOps (`gitops/`)

ArgoCD watches the `gitops/` folder. When you edit YAML files and push to Git, ArgoCD automatically applies the changes to Kubernetes. No manual `kubectl apply` needed!

## 📊 Grafana Dashboard Panels

| Panel | Description |
|-------|-------------|
| System Alert Level | GREEN/YELLOW/RED from AI analysis |
| Health Score | 0-100 score based on error/warning ratios |
| Log Entries by Level | Time-series showing INFO/WARN/ERROR/CRITICAL rates |
| Memory & CPU | Simulated system metrics |
| Error Rate | Percentage of requests resulting in errors |
| LLM Analysis Duration | How long each AI analysis takes |
| Request Duration P50/P95/P99 | Latency percentiles histogram |

## ⚙️ Configuration

All configuration is done via environment variables in the Kubernetes deployment manifests:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama-service:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | AI model to use |
| `LOG_GENERATOR_URL` | `http://log-generator-service:5000` | Log generator URL |
| `ANALYSIS_INTERVAL_SECONDS` | `60` | How often to run analysis |

## 🔄 CI/CD Pipeline

Every push to `main` branch:
1. **Lint**: Python code checked with flake8
2. **Build**: Docker images built for linux/amd64 and linux/arm64
3. **Push**: Images pushed to Docker Hub with `:latest` and commit SHA tags

Configure Docker Hub credentials in GitHub Settings → Secrets:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

## 📚 Learn More

- [docs/architecture-diagram.md](docs/architecture-diagram.md) - Visual system architecture
- [docs/workflow.md](docs/workflow.md) - Step-by-step data flow walkthrough
- [Ollama Models](https://ollama.ai/library) - Available AI models
- [KIND Documentation](https://kind.sigs.k8s.io/) - Local Kubernetes clusters
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/) - GitOps with ArgoCD
