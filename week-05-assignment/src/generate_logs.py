from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import random


OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "logs_sample.txt"
TOTAL_LOG_LINES = 250
RANDOM_SEED = 42


def build_log_line(
    timestamp: datetime,
    level: str,
    service: str,
    event: str,
    message: str,
) -> str:
    """Return one structured log line."""

    return (
        f"{timestamp.isoformat()} "
        f"level={level} "
        f"service={service} "
        f"event={event} "
        f'message="{message}"'
    )


def generate_logs() -> list[str]:
    """Generate realistic infrastructure and application logs."""

    rng = random.Random(RANDOM_SEED)

    start_time = datetime(2025, 10, 1, 8, 0, 0)

    services = [
        "api-gateway",
        "auth-service",
        "orders-service",
        "payments-service",
        "inventory-service",
        "postgres-db",
        "worker-service",
    ]

    normal_events = [
        ("INFO", "request_completed", "Request completed successfully"),
        ("INFO", "health_check", "Health check passed"),
        ("INFO", "database_query", "Database query completed"),
        ("INFO", "cache_hit", "Response returned from cache"),
        ("INFO", "job_completed", "Background job completed"),
        ("INFO", "login_success", "User authentication succeeded"),
    ]

    warning_events = [
        ("WARNING", "high_latency", "Request latency exceeded warning threshold"),
        ("WARNING", "cpu_pressure", "CPU utilization is above 75 percent"),
        ("WARNING", "memory_pressure", "Memory utilization is above 80 percent"),
        ("WARNING", "retry_attempt", "Transient failure triggered a retry"),
        ("WARNING", "connection_pool", "Database connection pool is nearly exhausted"),
    ]

    error_events = [
        ("ERROR", "database_timeout", "Database request timed out"),
        ("ERROR", "service_unavailable", "Upstream service is unavailable"),
        ("ERROR", "payment_failure", "Payment authorization failed"),
        ("ERROR", "authentication_failure", "Repeated authentication failures detected"),
        ("ERROR", "disk_full", "Disk utilization exceeded critical threshold"),
        ("ERROR", "api_error", "API returned HTTP 500"),
    ]

    lines: list[str] = []

    for index in range(TOTAL_LOG_LINES):
        timestamp = start_time + timedelta(seconds=index * 30)

        # Normal operation for most log entries
        if index < 120 or index > 165:
            roll = rng.random()

            if roll < 0.82:
                level, event, message = rng.choice(normal_events)
            elif roll < 0.95:
                level, event, message = rng.choice(warning_events)
            else:
                level, event, message = rng.choice(error_events)

        # Simulated incident window
        else:
            roll = rng.random()

            if roll < 0.20:
                level, event, message = rng.choice(normal_events)
            elif roll < 0.50:
                level, event, message = rng.choice(warning_events)
            else:
                level, event, message = rng.choice(error_events)

        service = rng.choice(services)

        # Add a correlated incident pattern around the incident window
        if 130 <= index <= 145:
            correlated_incident = [
                (
                    "WARNING",
                    "cpu_pressure",
                    "CPU utilization is above 90 percent",
                    "orders-service",
                ),
                (
                    "WARNING",
                    "connection_pool",
                    "Database connection pool is nearly exhausted",
                    "postgres-db",
                ),
                (
                    "ERROR",
                    "database_timeout",
                    "Database request timed out after 5000 milliseconds",
                    "orders-service",
                ),
                (
                    "ERROR",
                    "service_unavailable",
                    "Orders API dependency is unavailable",
                    "api-gateway",
                ),
            ]

            level, event, message, service = correlated_incident[
                (index - 130) % len(correlated_incident)
            ]

        lines.append(
            build_log_line(
                timestamp=timestamp,
                level=level,
                service=service,
                event=event,
                message=message,
            )
        )

    return lines


def main() -> None:
    """Generate and save the sample structured logs."""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = generate_logs()

    OUTPUT_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    warning_count = sum("level=WARNING" in line for line in lines)
    error_count = sum("level=ERROR" in line for line in lines)

    print(f"Wrote {len(lines)} structured log lines.")
    print(f"Warnings: {warning_count}")
    print(f"Errors: {error_count}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()