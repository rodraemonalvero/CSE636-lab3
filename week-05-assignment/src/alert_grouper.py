from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

ALERTS_PATH = PROJECT_ROOT / "output" / "detected_alerts.csv"
LOGS_PATH = PROJECT_ROOT / "data" / "logs_sample.txt"
OUTPUT_JSON = PROJECT_ROOT / "output" / "grouped_alerts.json"


def load_alerts() -> pd.DataFrame:
    """Load detected anomaly alerts."""

    if not ALERTS_PATH.exists():
        raise FileNotFoundError(
            f"Missing alerts file: {ALERTS_PATH}"
        )

    alerts = pd.read_csv(
        ALERTS_PATH,
        parse_dates=["timestamp"],
    )

    alerts = alerts.sort_values("timestamp").reset_index(drop=True)

    return alerts


def load_logs() -> list[str]:
    """Load structured logs."""

    if not LOGS_PATH.exists():
        raise FileNotFoundError(
            f"Missing log file: {LOGS_PATH}"
        )

    return LOGS_PATH.read_text(
        encoding="utf-8"
    ).splitlines()


def classify_alert(row: pd.Series) -> str:
    """Assign an incident category based on the strongest signal."""

    if row["error_rate"] >= 3:
        return "Application Errors"

    if row["cpu_pct"] >= 80:
        return "CPU Saturation"

    if row["mem_pct"] >= 65:
        return "Memory Pressure"

    if row["req_per_sec"] >= 450:
        return "Traffic Spike"

    return "General Infrastructure"


def collect_log_evidence(
    category: str,
    logs: list[str],
) -> list[str]:
    """Return up to five matching log lines."""

    keywords = {
        "Application Errors": [
            "ERROR",
            "database_timeout",
            "service_unavailable",
            "api_error",
        ],
        "CPU Saturation": [
            "cpu_pressure",
            "high_latency",
        ],
        "Memory Pressure": [
            "memory_pressure",
            "connection_pool",
        ],
        "Traffic Spike": [
            "request_completed",
            "high_latency",
        ],
        "General Infrastructure": [
            "WARNING",
            "ERROR",
        ],
    }

    matches: list[str] = []

    for line in logs:
        if any(keyword in line for keyword in keywords[category]):
            matches.append(line)

        if len(matches) == 5:
            break

    return matches


def build_sample_alerts(group: pd.DataFrame) -> list[dict]:
    """Convert sample alert rows into JSON-safe dictionaries."""

    sample_alerts: list[dict] = []

    for _, row in group.head(5).iterrows():
        sample_alerts.append(
            {
                "timestamp": row["timestamp"].isoformat(),
                "cpu_pct": float(row["cpu_pct"]),
                "mem_pct": float(row["mem_pct"]),
                "req_per_sec": float(row["req_per_sec"]),
                "error_rate": float(row["error_rate"]),
            }
        )

    return sample_alerts


def group_alerts(
    alerts: pd.DataFrame,
    logs: list[str],
) -> list[dict]:
    """Group alerts by incident category."""

    categorized_alerts = alerts.copy()

    categorized_alerts["incident_category"] = categorized_alerts.apply(
        classify_alert,
        axis=1,
    )

    grouped_incidents: list[dict] = []

    for category, group in categorized_alerts.groupby(
        "incident_category"
    ):
        grouped_incidents.append(
            {
                "incident": category,
                "alert_count": int(len(group)),
                "start_time": group["timestamp"].min().isoformat(),
                "end_time": group["timestamp"].max().isoformat(),
                "average_cpu_pct": round(
                    float(group["cpu_pct"].mean()),
                    2,
                ),
                "average_mem_pct": round(
                    float(group["mem_pct"].mean()),
                    2,
                ),
                "average_req_per_sec": round(
                    float(group["req_per_sec"].mean()),
                    2,
                ),
                "average_error_rate": round(
                    float(group["error_rate"].mean()),
                    2,
                ),
                "sample_alerts": build_sample_alerts(group),
                "related_logs": collect_log_evidence(
                    category,
                    logs,
                ),
            }
        )

    grouped_incidents.sort(
        key=lambda item: item["alert_count"],
        reverse=True,
    )

    return grouped_incidents


def save_groups(groups: list[dict]) -> None:
    """Write grouped alerts to JSON."""

    OUTPUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            groups,
            file,
            indent=4,
        )


def main() -> None:
    """Load, group, and export detected alerts."""

    alerts = load_alerts()
    logs = load_logs()

    print(f"Loaded {len(alerts)} detected alerts.")

    groups = group_alerts(
        alerts,
        logs,
    )

    save_groups(groups)

    print()
    print(f"Created {len(groups)} incident groups.")
    print()

    for group in groups:
        print(
            f"{group['incident']:<25}"
            f"{group['alert_count']:>5} alerts"
        )

    print()
    print(f"Saved: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()