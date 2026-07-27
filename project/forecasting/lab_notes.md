# Week 4 Lab Notes – Predictive Analytics for DevOps

## 1. What MAPE did you achieve? Is it good enough?

The forecasting model achieved a Mean Absolute Percentage Error (MAPE) of **7.1%** and a Mean Absolute Error (MAE) of **2.57% CPU**. Since the MAPE is below 10%, the forecast is accurate enough for this simulated workload. This level of accuracy is suitable for making proactive autoscaling decisions while still allowing some safety margin.

---

## 2. What patterns did Prophet reveal?

The Prophet model identified a clear daily seasonal pattern in CPU utilization. CPU usage followed a repeating cycle with higher utilization during busy periods and lower utilization during quieter periods. The trend also showed a gradual increase over time together with one noticeable CPU spike, demonstrating that Prophet can capture both long-term trends and recurring seasonal behavior.

---

## 3. What happens if CPU suddenly spikes to 95%?

If CPU utilization suddenly increases to 95%, the forecasting model may not immediately predict the spike because Prophet relies on historical patterns. The autoscaler could react too slowly if the spike is completely unexpected.

To improve the system, I would:

- Combine forecasting with real-time CPU monitoring.
- Use shorter prediction intervals.
- Add anomaly detection for unexpected spikes.
- Configure Kubernetes HPA or KEDA as a safety mechanism for immediate scaling.

This combination would provide proactive scaling while still responding quickly to sudden workload changes.