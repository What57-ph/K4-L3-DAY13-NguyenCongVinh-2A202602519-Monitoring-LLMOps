"""Operations-style six-panel dashboard for the Day 13 monitoring contract."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
SLO_CONFIG_PATH = REPO_ROOT / "config" / "slo.yaml"


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("dashboard"), dict):
        raise ValueError("dashboard.yaml must contain a dashboard object")
    return payload["dashboard"]


def load_slo(path: Path = SLO_CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_records(
    path: Path = LOG_PATH,
    *,
    window_minutes: int = 60,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = parse_timestamp(record.get("ts"))
        if isinstance(record, dict) and timestamp and timestamp >= cutoff:
            records.append(record)
    return records


def event_records(records: Iterable[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("event") == event]


def numeric_values(records: Iterable[dict[str, Any]], field: str) -> list[float]:
    return [
        float(record[field])
        for record in records
        if isinstance(record.get(field), (int, float))
    ]


def percentile(values: Iterable[float], quantile: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = min(
        len(ordered) - 1,
        max(0, round((quantile / 100) * len(ordered) + 0.5) - 1),
    )
    return ordered[index]


def minute_averages(records: Iterable[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = {}
    for record in records:
        timestamp = parse_timestamp(record.get("ts"))
        value = record.get(field)
        if not timestamp or not isinstance(value, (int, float)):
            continue
        minute = timestamp.astimezone(timezone.utc).strftime("%H:%M")
        buckets.setdefault(minute, []).append(float(value))

    return [
        {"minute": minute, field: round(statistics.mean(values), 3)}
        for minute, values in sorted(buckets.items())
    ]


def minute_counts(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = Counter()
    for record in records:
        timestamp = parse_timestamp(record.get("ts"))
        if timestamp:
            buckets[timestamp.astimezone(timezone.utc).strftime("%H:%M")] += 1
    return [{"minute": minute, "requests": count} for minute, count in sorted(buckets.items())]


def threshold_ok(value: float, threshold: dict[str, Any]) -> bool:
    operator = threshold.get("operator")
    target = float(threshold.get("value", 0))
    if operator == "lte":
        return value <= target
    if operator == "gte":
        return value >= target
    return False


def threshold_text(panel: dict[str, Any]) -> str:
    threshold = panel["threshold"]
    return (
        f"Threshold {threshold['aggregation']} "
        f"{threshold['operator']} {threshold['value']} {panel['unit']}"
    )


def inject_styles(st: Any) -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #08111f; color: #e6edf7; }
        .block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
        [data-testid="stMetric"] {
            background: #101d30; border: 1px solid #203450;
            border-radius: 12px; padding: 14px 16px;
        }
        [data-testid="stMetricLabel"] { color: #91a5c1; }
        [data-testid="stMetricValue"] { color: #f5f8fc; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #0d192a; border: 1px solid #203450;
            border-radius: 16px; padding: 8px 8px 4px 8px;
        }
        .hero {
            background: linear-gradient(120deg, #10233d 0%, #132d4b 55%, #143a4e 100%);
            border: 1px solid #28567b; border-radius: 18px;
            padding: 22px 26px; margin-bottom: 18px;
        }
        .hero h1 { color: #f5f8fc; font-size: 2rem; margin: 0 0 6px 0; }
        .hero p { color: #a9c0d8; margin: 0; }
        .panel-title { color: #eaf2fb; font-size: 1.05rem; font-weight: 650; margin: 2px 0; }
        .panel-subtitle { color: #7f96b3; font-size: .78rem; margin-bottom: 12px; }
        section[data-testid="stSidebar"] { background: #0a1626; border-right: 1px solid #203450; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def panel_header(st: Any, icon: str, panel: dict[str, Any], value: float) -> bool:
    ok = threshold_ok(value, panel["threshold"])
    status = "HEALTHY" if ok else "BREACHED"
    color = "#8ff0bd" if ok else "#ffb0a8"
    background = "#123c32" if ok else "#4a222b"
    st.markdown(
        f"""
        <div class="panel-title">{icon} {panel['title']}</div>
        <div class="panel-subtitle">{threshold_text(panel)}
        <span style="color:{color}; background:{background}; border-radius:999px;
        padding:4px 10px; font-size:.72rem; font-weight:700;">{status}</span></div>
        """,
        unsafe_allow_html=True,
    )
    return ok


def render_chart(st: Any, rows: list[dict[str, Any]], field: str) -> None:
    if rows:
        st.line_chart(rows, x="minute", y=field, height=170)


def render_dashboard(st: Any, dashboard: dict[str, Any]) -> None:
    records = load_records(window_minutes=int(dashboard["time_range_minutes"]))
    responses = event_records(records, "response_sent")
    requests = event_records(records, "request_received")
    failures = event_records(records, "request_failed")
    panels = {panel["id"]: panel for panel in dashboard["panels"]}
    slo = load_slo().get("primary_slo", {})
    latest = max((parse_timestamp(record.get("ts")) for record in records), default=None)

    st.markdown(
        f"""
        <div class="hero">
          <h1>◈ {dashboard['title']}</h1>
          <p>Operational view · logs.jsonl · last {dashboard['time_range_minutes']} minutes
          · SLO target {slo.get('target_percent', '—')}%</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    header_columns = st.columns([1, 1, 1, 2])
    header_columns[0].metric("Requests", len(requests))
    header_columns[1].metric("Responses", len(responses))
    header_columns[2].metric("Failed", len(failures))
    header_columns[3].markdown(
        f"<div style='color:#7f96b3;font-size:.8rem'>Last event: "
        f"{latest.isoformat() if latest else 'no data'} UTC<br>"
        f"Loaded records: {len(records)} · Source: data/logs.jsonl</div>",
        unsafe_allow_html=True,
    )

    if not records:
        st.warning(
            "Chưa có log trong cửa sổ hiện tại. Hãy chạy API và load test, "
            "sau đó bấm Refresh now."
        )

    latency_column, traffic_column = st.columns([2.1, 1], gap="large")
    with latency_column:
        with st.container(border=True):
            latency = numeric_values(responses, "latency_ms")
            ttft = numeric_values(responses, "ttft_ms")
            latency_p95 = percentile(latency, 95)
            panel_header(st, "◒", panels["latency"], latency_p95)
            metric_columns = st.columns(4)
            for column, label, value in zip(
                metric_columns,
                ("P50", "P95", "P99", "TTFT P95"),
                (
                    percentile(latency, 50),
                    latency_p95,
                    percentile(latency, 99),
                    percentile(ttft, 95),
                ),
            ):
                column.metric(label, f"{value:.0f} ms")
            render_chart(st, minute_averages(responses, "latency_ms"), "latency_ms")

    with traffic_column:
        with st.container(border=True):
            request_rate = len(requests) / max(1, int(dashboard["time_range_minutes"]))
            panel_header(st, "↗", panels["traffic"], request_rate)
            st.metric("Request rate", f"{request_rate:.2f}/min")
            st.caption(f"{len(requests)} requests in the selected window")
            render_chart(st, minute_counts(requests), "requests")

    errors_column, cost_column = st.columns([1.35, 1], gap="large")
    with errors_column:
        with st.container(border=True):
            error_rate = (len(failures) / len(requests) * 100) if requests else 0.0
            retrieval_records = [
                record for record in responses if record.get("tool_success") is not None
            ]
            retrieval_success = (
                sum(record.get("tool_success") is True for record in retrieval_records)
                / len(retrieval_records)
                * 100
                if retrieval_records
                else 0.0
            )
            panel_header(st, "⚠", panels["errors"], error_rate)
            metric_columns = st.columns(3)
            metric_columns[0].metric("Error rate", f"{error_rate:.2f}%")
            metric_columns[1].metric("Failed", len(failures))
            metric_columns[2].metric("Retrieval", f"{retrieval_success:.2f}%")
            if failures:
                breakdown = [
                    {"error_type": error_type, "count": count}
                    for error_type, count in Counter(
                        record.get("error_type", "unknown") for record in failures
                    ).items()
                ]
                st.dataframe(breakdown, hide_index=True, use_container_width=True)
            else:
                st.success("No failed requests in the selected window.")

    with cost_column:
        with st.container(border=True):
            total_cost = sum(numeric_values(responses, "cost_usd"))
            panel_header(st, "$", panels["cost"], total_cost)
            st.metric("Total cost", f"USD {total_cost:.6f}")
            render_chart(st, minute_averages(responses, "cost_usd"), "cost_usd")

    tokens_column, quality_column = st.columns(2, gap="large")
    with tokens_column:
        with st.container(border=True):
            input_tokens = sum(numeric_values(responses, "tokens_in"))
            output_tokens = sum(numeric_values(responses, "tokens_out"))
            token_total = input_tokens + output_tokens
            panel_header(st, "▦", panels["tokens"], token_total)
            metric_columns = st.columns(2)
            metric_columns[0].metric("Input", f"{input_tokens:,.0f}")
            metric_columns[1].metric("Output", f"{output_tokens:,.0f}")
            token_limit = float(panels["tokens"]["threshold"]["value"])
            st.progress(min(token_total / token_limit, 1.0) if token_limit else 0.0)
            st.caption(f"{token_total:,.0f} / {token_limit:,.0f} tokens")

    with quality_column:
        with st.container(border=True):
            quality = numeric_values(responses, "quality_score")
            quality_mean = statistics.mean(quality) if quality else 0.0
            panel_header(st, "✦", panels["quality"], quality_mean)
            st.metric("Mean quality", f"{quality_mean:.3f}")
            st.progress(max(0.0, min(quality_mean, 1.0)))
            st.caption("Heuristic quality score · target is configured in dashboard.yaml")

    with st.expander("Incident investigation helper"):
        st.write(
            "Lấy correlation_id từ request_failed hoặc response_sent bất thường, "
            "sau đó tìm cùng ID trong Langfuse để mở waterfall."
        )
        if failures:
            st.write(
                "Recent failed correlation IDs:",
                [record.get("correlation_id") for record in failures[-10:]],
            )

    st.caption(
        f"Refresh contract: {dashboard['refresh_seconds']} giây · "
        "Bấm Refresh now sau mỗi lần load test hoặc incident action để chụp evidence."
    )


def main() -> None:
    import streamlit as st

    dashboard = load_config()
    st.set_page_config(
        page_title=dashboard["title"],
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles(st)

    with st.sidebar:
        st.markdown("## ◈ Control room")
        st.caption("Day 13 · Monitoring & LLMOps")
        if st.button("↻  Refresh now", use_container_width=True):
            st.rerun()
        st.divider()
        st.markdown("**View settings**")
        st.write(f"Time range: {dashboard['time_range_minutes']} minutes")
        st.write(f"Refresh contract: {dashboard['refresh_seconds']} seconds")
        st.write("Data source: data/logs.jsonl")
        st.divider()
        st.info(
            "Dashboard chỉ đọc log. Điều tra sâu bằng correlation_id → Langfuse trace."
        )

    render_dashboard(st, dashboard)


if __name__ == "__main__":
    main()

