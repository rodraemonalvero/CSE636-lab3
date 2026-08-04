# Week 5 Assignment — Intelligent Anomaly Detection and AI-Generated Root Cause Analysis

## Overview

This project implements a small end-to-end anomaly detection and root cause analysis system for DevOps observability data.

The system:

1. Generates structured infrastructure logs.
2. Detects anomalies in synthetic metrics using Isolation Forest.
3. Evaluates the detector using precision, recall, and F1-score.
4. Groups related alerts into incident categories.
5. Uses an agentic RCA workflow with two tools:
   - metrics analysis
   - log analysis
6. Generates a structured root cause analysis report.
7. Emits and captures OpenTelemetry GenAI spans for the RCA workflow.

The project uses a simulated LLM-style RCA agent so it can run without paid API access while still demonstrating tool use, telemetry, token estimation, latency, and cost tracking.

---

## Project Structure

```text
week-05-assignment/
├── data/
│   ├── metrics_sample.csv
│   └── logs_sample.txt
├── notebooks/
│   └── analysis.ipynb
├── output/
│   ├── anomaly_metrics.csv
│   ├── anomaly_visualization.png
│   ├── detected_alerts.csv
│   ├── grouped_alerts.json
│   ├── rca_report.md
│   └── spans_sample.json
├── src/
│   ├── alert_grouper.py
│   ├── anomaly_detector.py
│   ├── generate_logs.py
│   ├── rca_agent.py
│   └── telemetry.py
├── README.md
└── requirements.txt