"""
prompt_builder.py - Builds AI Prompts from Log Data
------------------------------------------------------
This module takes raw log data and turns it into a well-structured
prompt (question/instruction) that the AI model can understand.

Why is prompt engineering important?
  The AI model is only as good as the instructions you give it.
  A well-written prompt helps the AI:
    1. Focus on what matters (errors and warnings)
    2. Give structured, actionable responses
    3. Avoid vague or unhelpful answers

This is called "prompt engineering" - one of the most important
skills in working with AI systems!
"""

import json
from typing import List, Dict, Any
from datetime import datetime, timezone


class PromptBuilder:
    """
    Converts raw log data into structured prompts for the AI model.
    
    The prompt tells the AI exactly what we want it to do:
    - Analyze log severity distribution
    - Identify patterns in errors
    - Suggest what might be wrong
    - Recommend actions for the DevOps team
    """

    def build_analysis_prompt(self, logs: List[Dict[str, Any]]) -> str:
        """
        Build a full analysis prompt from a list of log entries.
        
        Args:
            logs: List of log dictionaries from log_collector
            
        Returns:
            A string prompt ready to send to the AI model
        """
        if not logs:
            return self._build_empty_prompt()

        # Summarize log statistics
        stats = self._calculate_stats(logs)

        # Format log entries for the prompt (we don't want ALL logs - just key ones)
        log_sample = self._format_log_sample(logs)

        # Build the final prompt
        prompt = f"""You are an experienced DevOps Site Reliability Engineer (SRE) analyzing application logs.

=== LOG ANALYSIS REQUEST ===
Timestamp: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
Analysis Period: Last {len(logs)} log entries

=== LOG STATISTICS ===
Total Logs Analyzed: {stats['total']}
- INFO:     {stats['info']} ({stats['info_pct']:.1f}%)
- WARNING:  {stats['warning']} ({stats['warning_pct']:.1f}%)
- ERROR:    {stats['error']} ({stats['error_pct']:.1f}%)
- CRITICAL: {stats['critical']} ({stats['critical_pct']:.1f}%)

Health Score: {stats['health_score']}/100

=== RECENT LOG ENTRIES (Most Important First) ===
{log_sample}

=== YOUR TASK ===
Please provide a concise analysis in the following format:

**SYSTEM HEALTH**: [HEALTHY / DEGRADED / CRITICAL] - one sentence explanation

**KEY ISSUES DETECTED** (list up to 3):
1. [issue with brief explanation]
2. [issue with brief explanation]  
3. [issue with brief explanation]

**ROOT CAUSE HYPOTHESIS**:
[2-3 sentences explaining what might be causing any errors/warnings]

**RECOMMENDED ACTIONS** (list up to 3 actionable steps):
1. [action]
2. [action]
3. [action]

**ALERT LEVEL**: [GREEN / YELLOW / RED]

Keep your response concise and focused on actionable insights for the DevOps team.
"""
        return prompt

    def _calculate_stats(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from log entries."""
        total = len(logs)
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}

        for log in logs:
            level = log.get("level", "INFO")
            counts[level] = counts.get(level, 0) + 1

        # Calculate health score (100 = all INFO, 0 = all CRITICAL)
        # Penalize: WARNING=-5, ERROR=-20, CRITICAL=-50
        penalty = (
            counts["WARNING"] * 5 +
            counts["ERROR"] * 20 +
            counts["CRITICAL"] * 50
        )
        health_score = max(0, 100 - (penalty / max(total, 1)))

        return {
            "total": total,
            "info": counts["INFO"],
            "warning": counts["WARNING"],
            "error": counts["ERROR"],
            "critical": counts["CRITICAL"],
            "info_pct": (counts["INFO"] / total * 100) if total > 0 else 0,
            "warning_pct": (counts["WARNING"] / total * 100) if total > 0 else 0,
            "error_pct": (counts["ERROR"] / total * 100) if total > 0 else 0,
            "critical_pct": (counts["CRITICAL"] / total * 100) if total > 0 else 0,
            "health_score": round(health_score, 1),
        }

    def _format_log_sample(self, logs: List[Dict[str, Any]]) -> str:
        """
        Format log entries as readable text for the AI prompt.
        
        We prioritize CRITICAL and ERROR logs, include a few WARNINGs,
        and only a handful of INFOs to keep the prompt focused.
        """
        # Separate logs by priority
        critical_logs = [l for l in logs if l.get("level") == "CRITICAL"]
        error_logs    = [l for l in logs if l.get("level") == "ERROR"]
        warning_logs  = [l for l in logs if l.get("level") == "WARNING"]
        info_logs     = [l for l in logs if l.get("level") == "INFO"]

        # Take the most recent ones at each level
        selected = (
            critical_logs[-5:] +    # All CRITICAL (up to 5)
            error_logs[-8:] +       # Recent errors (up to 8)  
            warning_logs[-5:] +     # Recent warnings (up to 5)
            info_logs[-3:]          # Just a few INFO for context
        )

        # Format each entry
        lines = []
        for log in selected:
            timestamp = log.get("timestamp", "")[:19]  # Trim microseconds
            level = log.get("level", "INFO").ljust(8)   # Pad for alignment
            host = log.get("host", "unknown").ljust(10)
            message = log.get("message", "")
            lines.append(f"[{timestamp}] {level} [{host}] {message}")

        return "\n".join(lines) if lines else "No logs available"

    def _build_empty_prompt(self) -> str:
        """Prompt to use when no logs are available."""
        return """You are a DevOps SRE. No log data is currently available.
        
Please respond with:
**SYSTEM HEALTH**: UNKNOWN - No log data available for analysis
**ALERT LEVEL**: YELLOW
**RECOMMENDED ACTIONS**: 
1. Check if the log-generator service is running
2. Verify network connectivity between services
3. Check Kubernetes pod status with: kubectl get pods -n devops-platform
"""
