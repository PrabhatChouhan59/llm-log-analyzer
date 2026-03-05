"""
app.py - Log Generator Service
-------------------------------
This script simulates a real application by generating random log messages
at different severity levels (INFO, WARNING, ERROR, CRITICAL).

These logs are exposed via an HTTP endpoint so that the LLM Analyzer can
collect and analyze them.

How it works:
1. Every few seconds, a background thread generates a fake log entry.
2. Logs are stored in memory (a simple list).
3. A Flask web server exposes two endpoints:
   - GET /logs  → returns the last 100 log entries as JSON
   - GET /health → simple health check
"""

import time
import random
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify
from metrics import MetricsGenerator

# -------------------------------------------------------------------
# Setup Python's built-in logging so we can see output in the terminal
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Flask app - this is our tiny web server
# -------------------------------------------------------------------
app = Flask(__name__)

# In-memory log storage (last 500 entries)
log_store = []
MAX_LOGS = 500

# Lock for thread-safe access to log_store
log_lock = threading.Lock()

# ------------------------------------------------------------------
# Fake log message templates for different log levels
# ------------------------------------------------------------------
LOG_TEMPLATES = {
    "INFO": [
        "User {user_id} logged in successfully",
        "Processing request for endpoint /api/v1/{endpoint}",
        "Database query completed in {ms}ms",
        "Cache hit for key: user_session_{session_id}",
        "Successfully sent email to user {user_id}",
        "File upload completed: {filename}.pdf ({size}KB)",
        "Scheduled job 'cleanup_old_sessions' executed successfully",
        "API response time: {ms}ms for GET /api/users",
    ],
    "WARNING": [
        "Response time exceeded threshold: {ms}ms (limit: 500ms)",
        "Database connection pool at {pct}% capacity",
        "Rate limit approaching for IP: 192.168.{a}.{b}",
        "Memory usage at {pct}% on worker-{worker}",
        "Retry attempt {attempt}/3 for external API call",
        "Deprecated API endpoint /api/v0/{endpoint} called",
        "Cache miss rate elevated: {pct}% in last 5 minutes",
    ],
    "ERROR": [
        "Failed to connect to database after 3 retries",
        "Unhandled exception in /api/orders: NullPointerException",
        "Payment gateway timeout for transaction {txn_id}",
        "File not found: /data/uploads/{filename}.csv",
        "Authentication failed for user {user_id}: invalid token",
        "Service 'inventory-service' returned HTTP 503",
        "Redis connection refused on port 6379",
    ],
    "CRITICAL": [
        "DISK SPACE CRITICAL: Only {pct}% remaining on /dev/sda1",
        "Database primary node unreachable! Failover initiated.",
        "Memory usage at 98%! OOM killer may trigger soon.",
        "SSL certificate expires in {days} days!",
        "Security alert: Brute force detected from IP 10.0.{a}.{b}",
    ],
}

# Weights control how often each level appears (more INFO, fewer CRITICAL)
LOG_LEVEL_WEIGHTS = {
    "INFO": 60,
    "WARNING": 25,
    "ERROR": 12,
    "CRITICAL": 3,
}


def generate_fake_log():
    """
    Creates a single fake log entry with random data.
    Returns a dictionary representing the log.
    """
    # Pick a random log level based on weights
    levels = list(LOG_LEVEL_WEIGHTS.keys())
    weights = list(LOG_LEVEL_WEIGHTS.values())
    level = random.choices(levels, weights=weights, k=1)[0]

    # Pick a random message template for that level
    template = random.choice(LOG_TEMPLATES[level])

    # Fill in the template placeholders with random values
    message = template.format(
        user_id=random.randint(1000, 9999),
        endpoint=random.choice(["users", "orders", "products", "auth", "payments"]),
        ms=random.randint(10, 2000),
        session_id=random.randint(100000, 999999),
        filename=random.choice(["report", "invoice", "export", "backup"]),
        size=random.randint(10, 5000),
        pct=random.randint(50, 99),
        worker=random.randint(1, 8),
        attempt=random.randint(1, 3),
        txn_id=f"TXN{random.randint(100000, 999999)}",
        a=random.randint(1, 254),
        b=random.randint(1, 254),
        days=random.randint(1, 30),
    )

    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "log-generator",
        "message": message,
        "host": f"pod-{random.randint(1, 5)}",
    }

    return log_entry


def log_generation_loop():
    """
    Background thread that continuously generates logs.
    Runs forever; generates 1-3 logs every 2-5 seconds.
    """
    logger.info("Log generation thread started!")
    metrics = MetricsGenerator()

    while True:
        # Generate 1 to 3 log entries per cycle
        batch_size = random.randint(1, 3)

        with log_lock:
            for _ in range(batch_size):
                entry = generate_fake_log()
                log_store.append(entry)

                # Print to console as well
                logger.log(
                    getattr(logging, entry["level"], logging.INFO),
                    f"[{entry['host']}] {entry['message']}"
                )

            # Trim old logs to stay within MAX_LOGS limit
            if len(log_store) > MAX_LOGS:
                del log_store[:-MAX_LOGS]

        # Also update metrics
        metrics.update()

        # Wait between 2 and 5 seconds before next batch
        time.sleep(random.uniform(2, 5))


# ------------------------------------------------------------------
# Flask Routes (API Endpoints)
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint - Kubernetes uses this to check if the pod is alive."""
    return jsonify({"status": "healthy", "service": "log-generator"}), 200


@app.route("/logs", methods=["GET"])
def get_logs():
    """
    Returns the last 100 log entries as JSON.
    The LLM Analyzer calls this endpoint to fetch logs for analysis.
    """
    with log_lock:
        # Return a copy of the last 100 logs
        recent_logs = log_store[-100:]

    return jsonify({
        "count": len(recent_logs),
        "logs": recent_logs
    }), 200


@app.route("/logs/summary", methods=["GET"])
def get_summary():
    """Returns a quick count of logs by level."""
    with log_lock:
        summary = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        for entry in log_store:
            level = entry.get("level", "INFO")
            summary[level] = summary.get(level, 0) + 1

    return jsonify({
        "total_logs": len(log_store),
        "by_level": summary
    }), 200


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Start the background log generation thread
    thread = threading.Thread(target=log_generation_loop, daemon=True)
    thread.start()
    logger.info("Log Generator Service starting on port 5000...")

    # Start Flask web server
    # host="0.0.0.0" makes it accessible from outside the container
    app.run(host="0.0.0.0", port=5000, debug=False)
