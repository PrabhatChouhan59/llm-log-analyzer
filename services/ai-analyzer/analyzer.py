"""
analyzer.py - Main LLM Log Analyzer Service
---------------------------------------------
This is the heart of the LLM Analyzer service.
It orchestrates the entire analysis pipeline:

  1. Collect logs  →  LogCollector fetches from log-generator
  2. Build prompt  →  PromptBuilder formats logs for the AI
  3. Ask AI        →  OllamaClient sends prompt to Ollama
  4. Store result  →  Analysis is stored and exposed via API
  5. Expose metrics→  Results are pushed to Prometheus format
  6. Repeat        →  Runs on a schedule (every 60 seconds)

This file also runs a Flask web server to expose:
  - GET /analysis      → Latest AI analysis result
  - GET /health        → Service health check  
  - GET /metrics       → Prometheus metrics (for Grafana)
"""

import time
import logging
import threading
import os
from datetime import datetime, timezone
from flask import Flask, jsonify
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

from log_collector import LogCollector
from prompt_builder import PromptBuilder
from ollama_client import OllamaClient

# -------------------------------------------------------------------
# Configure logging (so we see what's happening in the terminal)
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Flask web server
# -------------------------------------------------------------------
app = Flask(__name__)

# -------------------------------------------------------------------
# Global state - stores the most recent analysis result
# (In production you'd use Redis or a database, but for learning,
# a simple dictionary works great!)
# -------------------------------------------------------------------
latest_analysis = {
    "timestamp": None,
    "status": "pending",    # pending | completed | error
    "result": None,
    "logs_analyzed": 0,
    "health_score": None,
    "alert_level": "UNKNOWN",
}

analysis_lock = threading.Lock()

# -------------------------------------------------------------------
# Prometheus Metrics
# These metrics will be scraped by Prometheus and shown in Grafana
# -------------------------------------------------------------------
ANALYSIS_TOTAL = Counter(
    "llm_analyses_total",
    "Total number of LLM analysis runs",
    ["status"]  # Labels: success / failure
)

ANALYSIS_DURATION = Gauge(
    "llm_analysis_duration_seconds",
    "Time taken for the last LLM analysis in seconds"
)

LOGS_ANALYZED = Gauge(
    "llm_logs_analyzed_count",
    "Number of logs analyzed in the last run"
)

ALERT_LEVEL = Gauge(
    "system_alert_level",
    "Current system alert level: 0=GREEN, 1=YELLOW, 2=RED, -1=UNKNOWN"
)

HEALTH_SCORE = Gauge(
    "system_health_score",
    "System health score from 0 (critical) to 100 (healthy)"
)


def map_alert_level(alert_str: str) -> int:
    """Convert alert level string to a number for Prometheus."""
    mapping = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    return mapping.get(alert_str.upper(), -1)


def extract_alert_level(analysis_text: str) -> str:
    """
    Parse the AI's response to extract the ALERT LEVEL.
    Looks for text like "**ALERT LEVEL**: RED"
    """
    if not analysis_text:
        return "UNKNOWN"

    text_upper = analysis_text.upper()
    if "ALERT LEVEL**: RED" in text_upper or "ALERT LEVEL: RED" in text_upper:
        return "RED"
    elif "ALERT LEVEL**: YELLOW" in text_upper or "ALERT LEVEL: YELLOW" in text_upper:
        return "YELLOW"
    elif "ALERT LEVEL**: GREEN" in text_upper or "ALERT LEVEL: GREEN" in text_upper:
        return "GREEN"
    else:
        return "UNKNOWN"


def run_analysis_cycle():
    """
    Runs a single complete analysis cycle:
    1. Fetch logs from log-generator
    2. Build a prompt
    3. Send to AI (Ollama)
    4. Store the result
    5. Update Prometheus metrics
    """
    global latest_analysis

    logger.info("=" * 50)
    logger.info("Starting new analysis cycle...")
    cycle_start = time.time()

    try:
        # Step 1: Collect logs
        collector = LogCollector()
        if not collector.check_health():
            logger.warning("Log generator service is not healthy - skipping cycle")
            return

        logs = collector.fetch_logs(limit=50)
        if not logs:
            logger.warning("No logs fetched - skipping AI analysis")
            return

        logger.info(f"Collected {len(logs)} log entries")

        # Step 2: Build the AI prompt
        builder = PromptBuilder()
        prompt = builder.build_analysis_prompt(logs)
        logger.info("Prompt built successfully")

        # Step 3: Send to AI
        ollama = OllamaClient()
        if not ollama.is_available():
            logger.error("Ollama is not available - cannot perform analysis")
            with analysis_lock:
                latest_analysis["status"] = "error"
                latest_analysis["result"] = "ERROR: Ollama service unavailable"
            ANALYSIS_TOTAL.labels(status="failure").inc()
            return

        logger.info("Sending logs to AI for analysis...")
        ai_response = ollama.generate_with_retry(prompt, max_retries=2)

        # Step 4: Parse and store result
        duration = round(time.time() - cycle_start, 2)
        alert_level = extract_alert_level(ai_response)

        with analysis_lock:
            latest_analysis = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "result": ai_response,
                "logs_analyzed": len(logs),
                "duration_seconds": duration,
                "alert_level": alert_level,
            }

        # Step 5: Update Prometheus metrics
        ANALYSIS_TOTAL.labels(status="success").inc()
        ANALYSIS_DURATION.set(duration)
        LOGS_ANALYZED.set(len(logs))
        ALERT_LEVEL.set(map_alert_level(alert_level))

        logger.info(f"✅ Analysis complete in {duration}s | Alert Level: {alert_level}")
        logger.info(f"AI Response Preview: {ai_response[:200]}...")

    except Exception as e:
        logger.error(f"Analysis cycle failed with unexpected error: {e}", exc_info=True)
        ANALYSIS_TOTAL.labels(status="failure").inc()
        with analysis_lock:
            latest_analysis["status"] = "error"
            latest_analysis["result"] = f"ERROR: {str(e)}"


def analysis_scheduler():
    """
    Background thread that runs analysis every N seconds.
    Like a cron job but inside the Python process.
    """
    # How often to run analysis (default: 60 seconds)
    interval = int(os.getenv("ANALYSIS_INTERVAL_SECONDS", "60"))
    logger.info(f"Analysis scheduler started. Running every {interval} seconds.")

    # Wait 10 seconds on startup to let Ollama model load
    logger.info("Waiting 10 seconds for services to stabilize...")
    time.sleep(10)

    while True:
        run_analysis_cycle()
        logger.info(f"Next analysis in {interval} seconds...")
        time.sleep(interval)


# -------------------------------------------------------------------
# Flask HTTP Routes
# -------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint - Kubernetes probes this to check if pod is alive."""
    return jsonify({
        "status": "healthy",
        "service": "llm-analyzer",
        "analysis_status": latest_analysis.get("status"),
    }), 200


@app.route("/analysis", methods=["GET"])
def get_analysis():
    """
    Returns the latest AI analysis result.
    Grafana dashboards and monitoring tools can call this.
    """
    with analysis_lock:
        result = dict(latest_analysis)
    return jsonify(result), 200


@app.route("/analysis/trigger", methods=["POST"])
def trigger_analysis():
    """
    Manually trigger an analysis cycle (useful for testing).
    POST /analysis/trigger
    """
    logger.info("Manual analysis trigger received!")
    thread = threading.Thread(target=run_analysis_cycle, daemon=True)
    thread.start()
    return jsonify({"message": "Analysis triggered! Check /analysis in ~30s"}), 202


@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Prometheus metrics endpoint.
    Prometheus scrapes this URL to collect our custom metrics.
    """
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# -------------------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 LLM Analyzer Service starting...")
    logger.info(f"  Ollama URL: {os.getenv('OLLAMA_URL', 'http://localhost:11434')}")
    logger.info(f"  Log Generator URL: {os.getenv('LOG_GENERATOR_URL', 'http://localhost:5000')}")

    # Start background analysis scheduler thread
    scheduler_thread = threading.Thread(target=analysis_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Flask API server on port 8080
    logger.info("API Server starting on port 8080...")
    app.run(host="0.0.0.0", port=8080, debug=False)
