# -----------------------------------------------------------
# Dockerfile for llm-analyzer service
# -----------------------------------------------------------

# Start from the official Python 3.11 slim image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install Python dependencies first (cached layer if requirements don't change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Port 8080 = Flask API (analysis results)
# Port 9090 = Prometheus metrics (additional scraping port)
EXPOSE 8080

# Set default environment variables
# These can be overridden in Kubernetes deployment manifests
ENV OLLAMA_URL=http://ollama-service:11434
ENV OLLAMA_MODEL=mistral
ENV LOG_GENERATOR_URL=http://log-generator-service:5000
ENV ANALYSIS_INTERVAL_SECONDS=60

# Start the analyzer
CMD ["python", "analyzer.py"]
