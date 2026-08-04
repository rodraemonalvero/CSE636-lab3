from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "metrics_sample.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"

ALERTS_PATH = OUTPUT_DIR / "detected_alerts.csv"
METRICS_PATH = OUTPUT_DIR / "anomaly_metrics.csv"
VISUALIZATION_PATH = OUTPUT_DIR / "anomaly_visualization.png"

FEATURES = [
    "cpu_pct",
    "mem_pct",
    "req_per_sec",
    "error_rate",
]

CONTAMINATION_VALUES = [0.01, 0.02, 0.10]
SELECTED_CONTAMINATION = 0.02
RANDOM_STATE = 42


def load_metrics() -> pd.DataFrame:
    """Load the synthetic metrics dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Metrics file was not found: {DATA_PATH}"
        )

    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])

    required_columns = {
        "timestamp",
        "cpu_pct",
        "mem_pct",
        "req_per_sec",
        "error_rate",
        "is_anomaly",
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            f"Metrics file is missing columns: {sorted(missing_columns)}"
        )

    return df


def evaluate_contamination(
    df: pd.DataFrame,
    contamination: float,
) -> dict[str, float | int]:
    """Train and evaluate one Isolation Forest configuration."""

    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES])

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=RANDOM_STATE,
    )

    predictions = model.fit_predict(X)
    predicted_labels = (predictions == -1).astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(
        df["is_anomaly"],
        predicted_labels,
        average="binary",
        zero_division=0,
    )

    true_positive = int(
        ((df["is_anomaly"] == 1) & (predicted_labels == 1)).sum()
    )

    false_positive = int(
        ((df["is_anomaly"] == 0) & (predicted_labels == 1)).sum()
    )

    false_negative = int(
        ((df["is_anomaly"] == 1) & (predicted_labels == 0)).sum()
    )

    return {
        "contamination": contamination,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "predicted_anomalies": int(predicted_labels.sum()),
    }


def train_selected_model(df: pd.DataFrame) -> pd.DataFrame:
    """Train the selected Isolation Forest and add prediction columns."""

    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES])

    model = IsolationForest(
        n_estimators=100,
        contamination=SELECTED_CONTAMINATION,
        random_state=RANDOM_STATE,
    )

    model.fit(X)

    output = df.copy()

    output["anomaly_score"] = model.decision_function(X)
    output["pred_anomaly"] = (
        model.predict(X) == -1
    ).astype(int)

    return output


def save_detected_alerts(df: pd.DataFrame) -> None:
    """Save predicted anomalies for the alert-grouping stage."""

    alerts = df[df["pred_anomaly"] == 1].copy()

    alert_columns = [
        "timestamp",
        "cpu_pct",
        "mem_pct",
        "req_per_sec",
        "error_rate",
        "is_anomaly",
        "pred_anomaly",
        "anomaly_score",
    ]

    alerts[alert_columns].to_csv(
        ALERTS_PATH,
        index=False,
    )


def save_visualization(df: pd.DataFrame) -> None:
    """Create and save an anomaly visualization."""

    anomaly_rows = df[df["pred_anomaly"] == 1]

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(15, 9),
        sharex=True,
    )

    axes[0].plot(
        df["timestamp"],
        df["cpu_pct"],
        linewidth=1,
        label="CPU %",
    )

    axes[0].scatter(
        anomaly_rows["timestamp"],
        anomaly_rows["cpu_pct"],
        s=18,
        label="Detected anomaly",
    )

    axes[0].set_title(
        "CPU Utilization with Isolation Forest Anomalies"
    )

    axes[0].set_ylabel("CPU %")
    axes[0].legend()
    axes[0].grid(True)

    axes[1].plot(
        df["timestamp"],
        df["error_rate"],
        linewidth=1,
        label="Error rate",
    )

    axes[1].scatter(
        anomaly_rows["timestamp"],
        anomaly_rows["error_rate"],
        s=18,
        label="Detected anomaly",
    )

    axes[1].set_title(
        "Application Error Rate with Isolation Forest Anomalies"
    )

    axes[1].set_ylabel("Error rate")
    axes[1].set_xlabel("Timestamp")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()

    fig.savefig(
        VISUALIZATION_PATH,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)


def main() -> None:
    """Run contamination tuning, detection, export, and visualization."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = load_metrics()

    print(f"Loaded {len(df)} metric rows.")
    print(
        f"Ground-truth anomalies: "
        f"{int(df['is_anomaly'].sum())}"
    )

    evaluation_rows = []

    for contamination in CONTAMINATION_VALUES:
        metrics = evaluate_contamination(
            df,
            contamination,
        )

        evaluation_rows.append(metrics)

        print(
            "contamination="
            f"{metrics['contamination']:.2f} "
            f"precision={metrics['precision']:.2f} "
            f"recall={metrics['recall']:.2f} "
            f"f1={metrics['f1']:.2f} "
            f"TP={metrics['true_positive']} "
            f"FP={metrics['false_positive']} "
            f"FN={metrics['false_negative']}"
        )

    evaluation_df = pd.DataFrame(evaluation_rows)

    evaluation_df.to_csv(
        METRICS_PATH,
        index=False,
    )

    detected_df = train_selected_model(df)

    save_detected_alerts(detected_df)
    save_visualization(detected_df)

    selected_metrics = evaluation_df[
        evaluation_df["contamination"]
        == SELECTED_CONTAMINATION
    ].iloc[0]

    print()
    print(
        "Selected contamination:",
        SELECTED_CONTAMINATION,
    )

    print(
        "Selected precision:",
        selected_metrics["precision"],
    )

    print(
        "Selected recall:",
        selected_metrics["recall"],
    )

    print(
        "Selected F1:",
        selected_metrics["f1"],
    )

    print()
    print(f"Saved alerts: {ALERTS_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved visualization: {VISUALIZATION_PATH}")


if __name__ == "__main__":
    main()