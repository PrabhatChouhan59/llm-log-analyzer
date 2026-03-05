"""
log_collector.py - Fetches Logs from Log Generator Service
------------------------------------------------------------
This module is responsible for connecting to the log-generator
service and fetching recent log entries.

In Kubernetes:
  The log-generator runs as a separate pod with a Service (like a stable
  network address). We call its HTTP API to get logs.

Think of this like a "news collector" that goes out and grabs the latest
headlines (logs) from another service.
"""

import requests
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class LogCollector:
    """
    Fetches log entries from the log-generator service via HTTP.
    """

    def __init__(self):
        # The URL of the log-generator service
        # In Kubernetes, services have stable DNS names like:
        #   http://<service-name>.<namespace>.svc.cluster.local:<port>
        self.log_service_url = os.getenv(
            "LOG_GENERATOR_URL",
            "http://localhost:5000"   # Default for local testing
        )
        self.timeout = 10  # seconds

        logger.info(f"LogCollector will fetch from: {self.log_service_url}")

    def fetch_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent log entries from the log-generator service.
        
        Args:
            limit: How many logs to return (default: 50)
            
        Returns:
            A list of log dictionaries, each containing:
            - timestamp: when the log was created
            - level: INFO/WARNING/ERROR/CRITICAL
            - service: which service generated it
            - message: the actual log message
            - host: which pod generated it
        """
        try:
            logger.info(f"Fetching logs from {self.log_service_url}/logs ...")
            response = requests.get(
                f"{self.log_service_url}/logs",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            all_logs = data.get("logs", [])

            # Return only the last `limit` entries
            recent_logs = all_logs[-limit:]
            logger.info(f"Successfully fetched {len(recent_logs)} log entries")
            return recent_logs

        except requests.ConnectionError:
            logger.error(
                f"Cannot connect to log-generator at {self.log_service_url}. "
                "Is the service running?"
            )
            return []
        except requests.Timeout:
            logger.error("Request to log-generator timed out")
            return []
        except requests.HTTPError as e:
            logger.error(f"HTTP error fetching logs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching logs: {e}")
            return []

    def fetch_summary(self) -> Dict[str, Any]:
        """
        Fetch a quick breakdown of log counts by level.
        
        Returns a dict like:
        {
            "total_logs": 245,
            "by_level": {"INFO": 150, "WARNING": 60, "ERROR": 30, "CRITICAL": 5}
        }
        """
        try:
            response = requests.get(
                f"{self.log_service_url}/logs/summary",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch log summary: {e}")
            return {}

    def check_health(self) -> bool:
        """
        Check if the log-generator service is reachable and healthy.
        Returns True if healthy, False otherwise.
        """
        try:
            response = requests.get(
                f"{self.log_service_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def get_logs_by_level(self, level: str) -> List[Dict[str, Any]]:
        """
        Filter fetched logs to only return entries of a specific level.
        
        Args:
            level: 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'
        """
        all_logs = self.fetch_logs(limit=100)
        filtered = [log for log in all_logs if log.get("level") == level.upper()]
        logger.info(f"Found {len(filtered)} logs with level={level}")
        return filtered
