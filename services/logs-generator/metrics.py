"""
metrics.py - Prometheus Metrics for Log Generator
---------------------------------------------------
This module exposes application metrics in Prometheus format.
Prometheus will "scrape" (pull) these metrics periodically.

Metrics exposed:
  - log_entries_total       : Counter of how many logs generated per level
  - active_connections      : Fake gauge for simulated active connections
  - request_duration_seconds: Histogram of simulated request durations
  - error_rate_percent      : Current error rate gauge

How Prometheus works (beginner explanation):
  Prometheus is a monitoring tool that pulls metrics from your app
  by hitting the /metrics endpoint. It stores the data and Grafana
  uses it to draw nice charts.
"""

import random
import time
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    start_http_server,
    REGISTRY,
)
import threading
import logging

logger = logging.getLogger(__name__)


class MetricsGenerator:
    """
    Manages all Prometheus metrics for the log-generator service.
    Each time update() is called, it simulates realistic-looking metrics.
    """

    def __init__(self):
        # ---------------------------------------------------------
        # Counter: only goes up (perfect for counting events)
        # ---------------------------------------------------------
        self.log_entries_total = Counter(
            "log_entries_total",
            "Total number of log entries generated",
            ["level"]   # Label: we track count per log level
        )

        # ---------------------------------------------------------
        # Gauge: can go up or down (perfect for current-state values)
        # ---------------------------------------------------------
        self.active_connections = Gauge(
            "active_connections",
            "Number of simulated active user connections"
        )

        self.memory_usage_percent = Gauge(
            "memory_usage_percent",
            "Simulated memory usage percentage"
        )

        self.cpu_usage_percent = Gauge(
            "cpu_usage_percent",
            "Simulated CPU usage percentage"
        )

        self.error_rate_percent = Gauge(
            "error_rate_percent",
            "Current error rate as a percentage of total requests"
        )

        self.db_connection_pool_usage = Gauge(
            "db_connection_pool_usage_percent",
            "Database connection pool usage percentage"
        )

        # ---------------------------------------------------------
        # Histogram: tracks distribution of values (great for latency)
        # ---------------------------------------------------------
        self.request_duration = Histogram(
            "request_duration_seconds",
            "Simulated HTTP request duration in seconds",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )

        # State variables to make metrics change realistically
        self._base_connections = random.randint(50, 200)
        self._base_memory = random.uniform(40, 70)
        self._error_spike = False
        self._spike_countdown = 0

        # Start Prometheus metrics server on port 8000
        self._start_metrics_server()

    def _start_metrics_server(self):
        """Start Prometheus HTTP server on port 8000 in a background thread."""
        try:
            start_http_server(8000)
            logger.info("Prometheus metrics available at http://0.0.0.0:8000/metrics")
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")

    def update(self):
        """
        Call this periodically to update all metric values.
        Simulates realistic fluctuations in system metrics.
        """
        # --- Simulate occasional error spikes ---
        if not self._error_spike and random.random() < 0.05:  # 5% chance of spike
            self._error_spike = True
            self._spike_countdown = random.randint(3, 8)

        if self._error_spike:
            error_rate = random.uniform(15, 45)
            self._spike_countdown -= 1
            if self._spike_countdown <= 0:
                self._error_spike = False
        else:
            error_rate = random.uniform(0, 5)

        # --- Update gauges with random-walk values ---
        # Connections drift around a base value
        connections = max(0, self._base_connections + random.randint(-20, 20))
        self.active_connections.set(connections)

        # Memory drifts slowly
        self._base_memory = min(95, max(20, self._base_memory + random.uniform(-2, 2)))
        self.memory_usage_percent.set(round(self._base_memory, 1))

        # CPU spikes during error periods
        cpu = random.uniform(60, 90) if self._error_spike else random.uniform(10, 50)
        self.cpu_usage_percent.set(round(cpu, 1))

        self.error_rate_percent.set(round(error_rate, 2))

        db_pool = random.uniform(20, 95) if self._error_spike else random.uniform(10, 60)
        self.db_connection_pool_usage.set(round(db_pool, 1))

        # --- Simulate some request durations (observe adds to histogram) ---
        num_requests = random.randint(1, 10)
        for _ in range(num_requests):
            # Most requests fast, some slow
            if random.random() < 0.9:
                duration = random.uniform(0.01, 0.5)
            else:
                duration = random.uniform(0.5, 5.0)
            self.request_duration.observe(duration)

        # --- Increment log counters by level ---
        for level, weight in [("INFO", 6), ("WARNING", 2), ("ERROR", 1), ("CRITICAL", 0)]:
            count = random.randint(0, weight)
            if count > 0:
                self.log_entries_total.labels(level=level).inc(count)
