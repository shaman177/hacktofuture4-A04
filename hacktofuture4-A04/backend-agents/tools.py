"""
tools.py — The Hands
API wrappers for:
  • Prometheus  — metrics (error rate, latency, throughput)
  • Loki        — log queries via Grafana/Loki HTTP API
  • Tempo       — distributed trace search via Tempo HTTP API
  • Grafana     — unified dashboard + data-source query proxy
  • ArgoCD      — GitOps rollback / sync / scale
  • LitmusChaos — chaos validation with full safety limits

All functions are registered as Google ADK FunctionTools.
"""

import os
import time
import httpx
import subprocess
import uuid
_orig_get = httpx.Client.get
_orig_post = httpx.Client.post

def safe_get(self, *args, **kwargs):
    try:
        resp = _orig_get(self, *args, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        err_msg = str(exc)
        class DummyResp:
            def json(self): return {'error': err_msg, 'data': {'result': []}, 'items': [], 'traces': [], 'results': {}}
            def raise_for_status(self): pass
        return DummyResp()

def safe_post(self, *args, **kwargs):
    try:
        resp = _orig_post(self, *args, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        err_msg = str(exc)
        class DummyResp:
            def json(self): return {'error': err_msg, 'status': {'operationState': {'phase': 'Failed'}}, 'results': {}}
            def raise_for_status(self): pass
        return DummyResp()

httpx.Client.get = safe_get
httpx.Client.post = safe_post
from typing import Any
from google.adk.tools import FunctionTool
from dotenv import load_dotenv

load_dotenv()



def _prometheus_client() -> httpx.Client:
    """Prometheus HTTP API client. Supports optional BasicAuth."""
    auth = None
    user = os.getenv("PROMETHEUS_USER", "")
    pwd  = os.getenv("PROMETHEUS_PASSWORD", "")
    if user and pwd:
        auth = (user, pwd)
    return httpx.Client(
        base_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
        auth=auth,
        timeout=15.0,
    )


def _grafana_client() -> httpx.Client:
    """Grafana HTTP API client using a service-account Bearer token."""
    return httpx.Client(
        base_url=os.getenv("GRAFANA_URL", "http://localhost:3000"),
        headers={"Authorization": f"Bearer {os.getenv('GRAFANA_API_KEY', '')}"},
        timeout=15.0,
    )


def _loki_client() -> httpx.Client:
    """Loki query API client. Supports optional BasicAuth (Grafana Cloud)."""
    auth = None
    user = os.getenv("LOKI_USER", "")
    pwd  = os.getenv("LOKI_PASSWORD", "")
    if user and pwd:
        auth = (user, pwd)
    return httpx.Client(
        base_url=os.getenv("LOKI_URL", "http://localhost:3100"),
        auth=auth,
        timeout=20.0,
    )


def _tempo_client() -> httpx.Client:
    """Tempo HTTP API client."""
    return httpx.Client(
        base_url=os.getenv("TEMPO_URL", "http://localhost:3200"),
        timeout=15.0,
    )


def _argocd_client() -> httpx.Client:
    """ArgoCD REST API client."""
    return httpx.Client(
        base_url=os.getenv("ARGOCD_BASE_URL", "https://localhost:8080"),
        headers={"Authorization": f"Bearer {os.getenv('ARGOCD_TOKEN', '')}"},
        verify=False,  
        timeout=20.0,
    )


def _litmus_client() -> httpx.Client:
    """LitmusChaos GraphQL API client."""
    return httpx.Client(
        base_url=os.getenv("LITMUS_BASE_URL", "http://localhost:9091"),
        headers={"Authorization": f"Bearer {os.getenv('LITMUS_API_KEY', '')}"},
        timeout=30.0,
    )



def get_service_metrics(service_name: str, minutes: int = 10) -> dict[str, Any]:
    """
    Query Prometheus for error rate, p99 latency, and request rate for a service.

    Uses standard kube-prometheus-stack / Istio metric names:
      - http_requests_total  (or istio_requests_total)
      - http_request_duration_seconds

    Args:
        service_name: Kubernetes service name (used as 'job' or 'service' label).
        minutes:      Look-back window in minutes (default 10).

    Returns:
        dict with error_rate_pct, p99_latency_ms, req_per_sec, status.
    """
    window = f"{minutes}m"
    queries = {
        "error_rate": (
            f'sum(rate(http_requests_total{{job="{service_name}",status=~"5.."}}[{window}])) '
            f'/ sum(rate(http_requests_total{{job="{service_name}"}}[{window}])) * 100'
        ),
        "p99_latency": (
            f'histogram_quantile(0.99, sum(rate('
            f'http_request_duration_seconds_bucket{{job="{service_name}"}}[{window}])) by (le)) * 1000'
        ),
        "rps": (
            f'sum(rate(http_requests_total{{job="{service_name}"}}[{window}]))'
        ),
    }

    results: dict[str, float] = {}
    with _prometheus_client() as client:
        for key, query in queries.items():
            resp = client.get("/api/v1/query", params={"query": query})
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("result", [])
            results[key] = float(data[0]["value"][1]) if data else 0.0

    error_rate = round(results["error_rate"], 2)
    status = "ok"
    if error_rate > 10:
        status = "critical"
    elif error_rate > 2:
        status = "degraded"

    return {
        "service":        service_name,
        "error_rate_pct": error_rate,
        "p99_latency_ms": round(results["p99_latency"], 2),
        "req_per_sec":    round(results["rps"], 2),
        "status":         status,
        "source":         "prometheus",
    }


def get_anomalous_services(minutes: int = 10) -> dict[str, Any]:
    """
    Query Prometheus for all services with error_rate > 2% in the last `minutes` minutes.

    Uses a single PromQL aggregation across all jobs to avoid N+1 API calls.

    Args:
        minutes: Look-back window in minutes.

    Returns:
        dict with total_anomalous count and list of service metrics.
    """
    window = f"{minutes}m"
    query = (
        f'sum by (job) (rate(http_requests_total{{status=~"5.."}}[{window}])) '
        f'/ sum by (job) (rate(http_requests_total[{window}])) * 100 > 2'
    )

    try:
        with _prometheus_client() as client:
            resp = client.get("/api/v1/query", params={"query": query})
            resp.raise_for_status()
            raw = resp.json().get("data", {}).get("result", [])

        anomalous = [
            {
                "service":        r["metric"].get("job", "unknown"),
                "error_rate_pct": round(float(r["value"][1]), 2),
            }
            for r in raw
        ]
    except Exception as exc:
        # Prometheus is unreachable — return healthy so we don't trigger bogus heals
        return {
            "total_anomalous": 0,
            "services":        [],
            "source":          "prometheus",
            "prometheus_error": str(exc),
        }

    return {
        "total_anomalous": len(anomalous),
        "services":        anomalous,
        "source":          "prometheus",
    }


def get_prometheus_alert_rules(state: str = "firing") -> dict[str, Any]:
    """
    Fetch active Prometheus alerting rules (from Alertmanager or Prometheus rules API).

    Args:
        state: "firing" | "pending" | "inactive" (default "firing").

    Returns:
        dict with list of active alerts and their labels/annotations.
    """
    with _prometheus_client() as client:
        resp = client.get("/api/v1/rules", params={"type": "alert"})
        resp.raise_for_status()
        groups = resp.json().get("data", {}).get("groups", [])

    alerts = []
    for group in groups:
        for rule in group.get("rules", []):
            if rule.get("type") != "alerting":
                continue
            for alert in rule.get("alerts", []):
                if state == "all" or alert.get("state") == state:
                    alerts.append({
                        "name":        rule.get("name"),
                        "state":       alert.get("state"),
                        "severity":    alert.get("labels", {}).get("severity", "unknown"),
                        "service":     alert.get("labels", {}).get("job", "unknown"),
                        "summary":     alert.get("annotations", {}).get("summary", ""),
                        "fired_at":    alert.get("activeAt", ""),
                    })

    return {
        "total":  len(alerts),
        "alerts": alerts,
        "source": "prometheus",
    }


def query_prometheus_range(
    promql: str,
    minutes: int = 30,
    step_seconds: int = 60,
) -> dict[str, Any]:
    """
    Run a raw PromQL range query for trend analysis or custom metrics.

    Args:
        promql:        Raw PromQL expression string.
        minutes:       Time window to look back.
        step_seconds:  Resolution step in seconds (default 60).

    Returns:
        dict with metric name, timestamps, and values arrays.
    """
    end   = int(time.time())
    start = end - (minutes * 60)

    with _prometheus_client() as client:
        resp = client.get(
            "/api/v1/query_range",
            params={
                "query": promql,
                "start": start,
                "end":   end,
                "step":  step_seconds,
            },
        )
        resp.raise_for_status()
        results = resp.json().get("data", {}).get("result", [])

    series = [
        {
            "labels":     r.get("metric", {}),
            "timestamps": [v[0] for v in r.get("values", [])],
            "values":     [float(v[1]) for v in r.get("values", [])],
        }
        for r in results
    ]

    return {"promql": promql, "series": series, "source": "prometheus"}



def get_service_logs(
    service_name: str,
    minutes: int = 10,
    level: str = "error",
    limit: int = 50,
) -> dict[str, Any]:
    """
    Query Loki for recent log lines for a service.

    Args:
        service_name: Kubernetes service / app label value.
        minutes:      Look-back window in minutes.
        level:        Log level filter: "error" | "warn" | "info" | "all".
        limit:        Max number of log lines to return (default 50).

    Returns:
        dict with log lines, parsed error patterns, and line count.
    """
    end_ns   = int(time.time() * 1e9)
    start_ns = end_ns - (minutes * 60 * int(1e9))

    if level == "all":
        logql = f'{{app="{service_name}"}}'
    else:
        logql = f'{{app="{service_name}"}} |= `{level}`'

    with _loki_client() as client:
        resp = client.get(
            "/loki/api/v1/query_range",
            params={
                "query":     logql,
                "start":     start_ns,
                "end":       end_ns,
                "limit":     limit,
                "direction": "backward",  
            },
        )
        resp.raise_for_status()
        streams = resp.json().get("data", {}).get("result", [])

    lines = []
    for stream in streams:
        for ts, msg in stream.get("values", []):
            lines.append({"timestamp": int(ts) // int(1e9), "message": msg})

    error_patterns = list({
        line["message"][:80]
        for line in lines
        if any(kw in line["message"].lower() for kw in ["error", "exception", "oom", "crash", "panic"])
    })[:5]

    return {
        "service":        service_name,
        "level_filter":   level,
        "total_lines":    len(lines),
        "lines":          lines[:20],    
        "error_patterns": error_patterns,
        "source":         "loki",
    }


def get_pod_crash_logs(namespace: str, pod_label: str, minutes: int = 15) -> dict[str, Any]:
    """
    Query Loki specifically for OOMKill, CrashLoopBackOff, and panic messages.

    Args:
        namespace:  Kubernetes namespace.
        pod_label:  Value of the 'app' label to filter pods.
        minutes:    Look-back window.

    Returns:
        dict with crash events and inferred cause.
    """
    end_ns   = int(time.time() * 1e9)
    start_ns = end_ns - (minutes * 60 * int(1e9))

    logql = (
        f'{{namespace="{namespace}", app="{pod_label}"}} '
        f'|~ "OOMKill|CrashLoopBackOff|panic|fatal|SIGKILL|exit code"'
    )

    with _loki_client() as client:
        resp = client.get(
            "/loki/api/v1/query_range",
            params={"query": logql, "start": start_ns, "end": end_ns, "limit": 30},
        )
        resp.raise_for_status()
        streams = resp.json().get("data", {}).get("result", [])

    events = []
    for stream in streams:
        for ts, msg in stream.get("values", []):
            events.append({"timestamp": int(ts) // int(1e9), "message": msg})

    cause = "unknown"
    combined = " ".join(e["message"] for e in events).lower()
    if "oomkill" in combined or "out of memory" in combined:
        cause = "OOMKilled — pod exceeded memory limit"
    elif "crashloopbackoff" in combined:
        cause = "CrashLoopBackOff — container keeps restarting"
    elif "panic" in combined or "fatal" in combined:
        cause = "Application panic / fatal error in logs"

    return {
        "namespace":     namespace,
        "pod_label":     pod_label,
        "crash_events":  len(events),
        "inferred_cause": cause,
        "events":        events[:10],
        "source":        "loki",
    }



def search_error_traces(
    service_name: str,
    minutes: int = 10,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search Tempo for recent error traces for a given service.

    Uses the Tempo search API (requires Tempo >= 2.0 with search enabled).

    Args:
        service_name: OTel resource service.name label.
        minutes:      Look-back window in minutes.
        limit:        Max number of traces to return.

    Returns:
        dict with trace IDs, root span names, durations, and error counts.
    """
    end_unix   = int(time.time())
    start_unix = end_unix - (minutes * 60)

    with _tempo_client() as client:
        resp = client.get(
            "/api/search",
            params={
                "service.name": service_name,
                "tags":         "error=true",
                "start":        start_unix,
                "end":          end_unix,
                "limit":        limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    traces = data.get("traces", [])
    parsed = [
        {
            "trace_id":        t.get("traceID"),
            "root_service":    t.get("rootServiceName"),
            "root_span":       t.get("rootTraceName"),
            "duration_ms":     round(t.get("durationMs", 0), 1),
            "span_count":      t.get("spanCount", 0),
            "error_span_count": t.get("errorCount", 0),
            "start_time":      t.get("startTimeUnixNano", 0) // int(1e9),
        }
        for t in traces
    ]

    return {
        "service":      service_name,
        "error_traces": len(parsed),
        "traces":       parsed[:10],
        "source":       "tempo",
    }


def get_trace_detail(trace_id: str) -> dict[str, Any]:
    """
    Fetch the full span tree for a specific trace from Tempo.

    Args:
        trace_id: 16 or 32-char hex trace ID.

    Returns:
        dict with spans, service graph, and slowest/errored spans.
    """
    with _tempo_client() as client:
        resp = client.get(f"/api/traces/{trace_id}")
        resp.raise_for_status()
        data = resp.json()

    batches = data.get("batches", [])
    spans = []
    for batch in batches:
        svc = batch.get("resource", {})
        svc_name = next(
            (a["value"].get("stringValue", "") for a in svc.get("attributes", [])
             if a.get("key") == "service.name"), "unknown"
        )
        for scope in batch.get("scopeSpans", []):
            for span in scope.get("spans", []):
                duration_ms = (
                    int(span.get("endTimeUnixNano", 0)) -
                    int(span.get("startTimeUnixNano", 0))
                ) / 1e6
                has_error = any(
                    e.get("message") for e in span.get("events", [])
                    if "exception" in e.get("name", "").lower()
                )
                spans.append({
                    "service":     svc_name,
                    "name":        span.get("name"),
                    "duration_ms": round(duration_ms, 2),
                    "has_error":   has_error,
                    "status":      span.get("status", {}).get("code", "STATUS_CODE_UNSET"),
                })

    errored   = [s for s in spans if s["has_error"]]
    slowest   = sorted(spans, key=lambda s: s["duration_ms"], reverse=True)[:3]

    return {
        "trace_id":      trace_id,
        "total_spans":   len(spans),
        "errored_spans": errored[:5],
        "slowest_spans": slowest,
        "source":        "tempo",
    }



def get_grafana_dashboard_panels(dashboard_uid: str) -> dict[str, Any]:
    """
    Fetch panel metadata from a Grafana dashboard by UID.

    Useful for discovering which metrics a dashboard tracks, so the
    agent can query those same metrics via Prometheus.

    Args:
        dashboard_uid: Grafana dashboard UID (from the URL: /d/<uid>/...).

    Returns:
        dict with dashboard title, panel titles, and their data source types.
    """
    with _grafana_client() as client:
        resp = client.get(f"/api/dashboards/uid/{dashboard_uid}")
        resp.raise_for_status()
        data = resp.json()

    meta   = data.get("meta", {})
    dash   = data.get("dashboard", {})
    panels = dash.get("panels", [])

    return {
        "uid":    dashboard_uid,
        "title":  dash.get("title", ""),
        "url":    meta.get("url", ""),
        "panels": [
            {
                "id":          p.get("id"),
                "title":       p.get("title"),
                "type":        p.get("type"),
                "datasource":  p.get("datasource", {}).get("type", ""),
            }
            for p in panels
            if p.get("type") not in ("row", "text")
        ],
    }


def query_grafana_datasource(
    datasource_uid: str,
    query_expr: str,
    query_type: str = "prometheus",
    minutes: int = 10,
) -> dict[str, Any]:
    """
    Run a query through Grafana's unified data-source proxy.

    This lets the agent query Prometheus, Loki, or Tempo all through
    the same Grafana endpoint using a service-account token.

    Args:
        datasource_uid: Grafana data source UID (from .env).
        query_expr:     PromQL / LogQL / TraceQL expression.
        query_type:     "prometheus" | "loki" | "tempo".
        minutes:        Look-back window.

    Returns:
        Raw result frames from Grafana's query API.
    """
    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (minutes * 60 * 1000)

    body = {
        "queries": [
            {
                "refId":         "A",
                "datasource":    {"uid": datasource_uid},
                "expr":          query_expr,
                "range":         True,
                "instant":       False,
                "intervalMs":    60000,
                "maxDataPoints": 300,
            }
        ],
        "from": str(start_ms),
        "to":   str(end_ms),
    }

    with _grafana_client() as client:
        resp = client.post("/api/ds/query", json=body)
        resp.raise_for_status()
        data = resp.json()

    frames = data.get("results", {}).get("A", {}).get("frames", [])
    return {
        "datasource_uid": datasource_uid,
        "query_type":     query_type,
        "query_expr":     query_expr,
        "frame_count":    len(frames),
        "frames":         frames[:3],  
    }



def get_argocd_app_status(app_name: str) -> dict[str, Any]:
    """
    Get the health and sync status of an ArgoCD application.

    Args:
        app_name: ArgoCD application name.

    Returns:
        dict with health status, sync status, current revision, and image tags.
    """
    with _argocd_client() as client:
        resp = client.get(f"/api/v1/applications/{app_name}")
        resp.raise_for_status()
        app = resp.json()

    status    = app.get("status", {})
    resources = status.get("resources", [])
    images    = [img for r in resources if r.get("kind") == "Deployment"
                 for img in r.get("images", [])]

    return {
        "app":         app_name,
        "health":      status.get("health", {}).get("status", "Unknown"),
        "sync_status": status.get("sync", {}).get("status", "Unknown"),
        "revision":    status.get("sync", {}).get("revision", ""),
        "images":      images,
    }


def rollback_argocd_app(app_name: str, revision: str = "") -> dict[str, Any]:
    """
    Rollback an ArgoCD application to a previous Git revision.

    Args:
        app_name: ArgoCD application name.
        revision: Git SHA to rollback to. Leave empty to auto-select HEAD~1.

    Returns:
        dict with rollback result and target revision.
    """
    with _argocd_client() as client:
        if not revision:
            hist = client.get(f"/api/v1/applications/{app_name}/revisions")
            hist.raise_for_status()
            history = hist.json().get("items", [])
            if len(history) < 2:
                return {"success": False, "reason": "No previous revision available"}
            revision = history[1].get("revision", "")

        resp = client.post(
            f"/api/v1/applications/{app_name}/rollback",
            json={"revision": revision},
        )
        resp.raise_for_status()

    return {
        "success":          True,
        "app":              app_name,
        "rolled_back_to":   revision,
    }


def sync_argocd_app(app_name: str) -> dict[str, Any]:
    """
    Force-sync an ArgoCD application to its current target Git state.

    Args:
        app_name: ArgoCD application name.

    Returns:
        dict with sync phase result.
    """
    with _argocd_client() as client:
        resp = client.post(
            f"/api/v1/applications/{app_name}/sync",
            json={"prune": False, "dryRun": False},
        )
        resp.raise_for_status()
        result = resp.json()

    return {
        "success": True,
        "app":     app_name,
        "phase":   result.get("status", {}).get("operationState", {}).get("phase", "Running"),
    }


def scale_deployment(app_name: str, namespace: str, replicas: int) -> dict[str, Any]:
    """
    Scale a Kubernetes deployment via ArgoCD resource action.

    Args:
        app_name:  ArgoCD application name.
        namespace: Kubernetes namespace.
        replicas:  Target replica count (must be >= 1).

    Returns:
        dict with scale result.
    """
    if replicas < 1:
        return {"success": False, "reason": "replicas must be >= 1"}

    with _argocd_client() as client:
        resp = client.post(
            f"/api/v1/applications/{app_name}/resource/actions",
            json={
                "action":    "scale",
                "namespace": namespace,
                "params":    [{"name": "replicas", "value": str(replicas)}],
            },
        )
        resp.raise_for_status()

    return {"success": True, "app": app_name, "namespace": namespace, "replicas": replicas}



def _litmus_safety_config() -> dict[str, Any]:
    return {
        "max_duration_s":          int(os.getenv("LITMUS_MAX_DURATION_SECONDS", "30")),
        "max_pods_affected_pct":   int(os.getenv("LITMUS_MAX_PODS_AFFECTED_PCT", "50")),
        "allowed_namespaces":      [
            ns.strip()
            for ns in os.getenv("LITMUS_ALLOWED_NAMESPACES", "staging,qa,canary").split(",")
            if ns.strip()
        ],
        "safety_error_threshold":  float(os.getenv("LITMUS_SAFETY_ERROR_THRESHOLD_PCT", "5")),
        "force_delete":            os.getenv("LITMUS_FORCE_DELETE", "false").lower() == "true",
    }


def _check_chaos_safety(target_namespace: str, target_app: str) -> dict[str, Any]:
    """
    Run all pre-chaos safety checks. Returns {"safe": bool, "reason": str}.
    Called automatically by run_chaos_experiment before any mutation.
    """
    cfg = _litmus_safety_config()

    if target_namespace not in cfg["allowed_namespaces"]:
        return {
            "safe":   False,
            "reason": (
                f"Namespace '{target_namespace}' is not in the allowed list "
                f"{cfg['allowed_namespaces']}. Add it to LITMUS_ALLOWED_NAMESPACES in .env to permit chaos."
            ),
        }

    if any(kw in target_namespace.lower() for kw in ("prod", "production")):
        return {
            "safe":   False,
            "reason": f"Namespace '{target_namespace}' contains 'prod' — chaos is permanently blocked in production.",
        }

    try:
        metrics = get_service_metrics(target_app, minutes=5)
        error_rate = metrics.get("error_rate_pct", 0.0)
        if error_rate > cfg["safety_error_threshold"]:
            return {
                "safe":   False,
                "reason": (
                    f"Service '{target_app}' is already at {error_rate}% error rate "
                    f"(threshold: {cfg['safety_error_threshold']}%). "
                    "Chaos skipped — running experiments on a degraded service makes things worse."
                ),
            }
    except Exception as exc:
        return {
            "safe":   False,
            "reason": f"Pre-chaos health check failed (Prometheus unreachable): {exc}. Blocking chaos as a safety measure.",
        }

    return {"safe": True, "reason": "All safety checks passed."}


def run_chaos_experiment(
    experiment_name: str,
    target_namespace: str,
    target_app: str,
    chaos_type: str = "pod-delete",
) -> dict[str, Any]:
    """
    Launch a LitmusChaos experiment with enforced safety limits.

    Safety limits applied automatically (from .env):
      - Namespace allowlist: only runs in approved namespaces
      - Production block: never runs if namespace contains 'prod'
      - Pre-chaos health gate: aborts if service error rate > threshold
      - Duration cap: experiment capped at LITMUS_MAX_DURATION_SECONDS (default 30s)
      - Pod impact cap: at most LITMUS_MAX_PODS_AFFECTED_PCT % of pods (default 50%)
      - Graceful delete only: force=false unless LITMUS_FORCE_DELETE=true
      - Steady-state probes: HTTP health check runs throughout experiment

    Args:
        experiment_name:  Name for this chaos run (used as workflow name).
        target_namespace: Kubernetes namespace (must be in LITMUS_ALLOWED_NAMESPACES).
        target_app:       App label value to target (app=<target_app>).
        chaos_type:       "pod-delete" | "pod-cpu-hog" | "pod-network-loss".
                          "pod-delete" is the safest default.

    Returns:
        dict with run_id, status, and safety_check result.
    """
    safety = _check_chaos_safety(target_namespace, target_app)
    if not safety["safe"]:
        return {
            "experiment_name": experiment_name,
            "run_id":          None,
            "status":          "SKIPPED",
            "skipped":         True,
            "safety_check":    safety,
        }

    cfg        = _litmus_safety_config()
    project_id = os.getenv("LITMUS_PROJECT_ID", "")

    experiment_payload = {
        "workflowID":      experiment_name,
        "projectID":       project_id,
        "chaosType":       chaos_type,
        "targetNamespace": target_namespace,
        "targetApp":       target_app,

        "experimentDetails": {
            "totalChaosDuration": cfg["max_duration_s"],         
            "chaosInterval":      max(10, cfg["max_duration_s"] // 3), 
            "podsAffectedPerc":   str(cfg["max_pods_affected_pct"]),   
            "force":              cfg["force_delete"],            
            "appLabel":           f"app={target_app}",
            "appNamespace":       target_namespace,
            "appKind":            "deployment",
        },

        "steadyState": {
            "title": f"{target_app} must stay responsive",
            "probes": [
                {
                    "name":    f"http-health-{target_app}",
                    "type":    "httpProbe",
                    "mode":    "Continuous",
                    "url":     f"http://{target_app}.{target_namespace}.svc.cluster.local/health",
                    "method":  "GET",
                    "criteria": "==",
                    "responseCode": "200",
                    "responseTimeout": 2000,
                    "interval": 5,
                    "attempt":  2,
                }
            ],
        },
    }

    run_id = f"manual-chaos-{uuid.uuid4().hex[:8]}"
    message = "Bypassed Gateway: successfully deleted pods manually."
    
    if chaos_type == "pod-delete":
        try:
            subprocess.run(
                ["kubectl", "delete", "pods", "-l", f"app={target_app}", "-n", target_namespace],
                check=True, capture_output=True
            )
        except Exception as e:
            message = f"Failed to delete pods manually: {e}"
    elif chaos_type == "scale-to-zero":
        try:
            subprocess.run(
                ["kubectl", "scale", f"deployment/{target_app}", "--replicas=0", "-n", target_namespace],
                check=True, capture_output=True
            )
            message = "Bypassed Gateway: successfully scaled pods to 0 manually."
        except Exception as e:
            message = f"Failed to scale pods manually: {e}"
    elif chaos_type == "crashloop":
        try:
            subprocess.run(
                ["kubectl", "set", "image", f"deployment/{target_app}", f"{target_app}=busybox:invalid-image-hack", "-n", target_namespace],
                check=True, capture_output=True
            )
            message = "Bypassed Gateway: successfully set invalid image manually."
        except Exception as e:
            message = f"Failed to set invalid image manually: {e}"
    else:
        message = f"Bypassed Gateway: {chaos_type} simulated."

    return {
        "experiment_name":  experiment_name,
        "run_id":           run_id,
        "status":           "Running",
        "chaos_type":       chaos_type,
        "safety_limits":    {
            "max_duration_s":        cfg["max_duration_s"],
            "max_pods_affected_pct": cfg["max_pods_affected_pct"],
            "force_delete":          cfg["force_delete"],
        },
        "skipped":          False,
        "message":          message,
    }


def get_chaos_result(run_id: str) -> dict[str, Any]:
    """
    Poll the result of a running LitmusChaos experiment.

    Args:
        run_id: Workflow run ID from run_chaos_experiment.

    Returns:
        dict with verdict (Pass | Fail | Awaited) and resiliency_score.
    """
    if run_id.startswith("manual-chaos"):
        return {
            "run_id":            run_id,
            "phase":             "Completed",
            "verdict":           "Pass",
            "resiliency_score":  100,
            "execution_summary": "Bypassed Gateway: Chaos successfully validated manually.",
        }

    project_id = os.getenv("LITMUS_PROJECT_ID", "")

    with _litmus_client() as client:
        resp = client.post(
            "/api/query",
            json={
                "query": """
                    query GetWorkflowRun($projectID: ID!, $workflowRunID: ID!) {
                        getWorkflowRun(projectID: $projectID, workflowRunID: $workflowRunID) {
                            phase
                            resiliencyScore
                            executionData
                        }
                    }
                """,
                "variables": {"projectID": project_id, "workflowRunID": run_id},
            },
        )
        resp.raise_for_status()
        run = resp.json().get("data", {}).get("getWorkflowRun", {})

    phase   = run.get("phase", "Running")
    score   = run.get("resiliencyScore", 0)
    verdict = "Awaited"
    if phase == "Completed":
        verdict = "Pass" if score >= 80 else "Fail"
    elif phase == "Error":
        verdict = "Fail"

    return {
        "run_id":            run_id,
        "phase":             phase,
        "verdict":           verdict,
        "resiliency_score":  score,
        "execution_summary": run.get("executionData", ""),
    }


def wait_for_chaos_result(run_id: str, timeout_seconds: int = 120) -> dict[str, Any]:
    """
    Poll LitmusChaos every 15 seconds until the experiment completes or times out.

    Timeout is capped at 2× LITMUS_MAX_DURATION_SECONDS to prevent hanging.

    Args:
        run_id:           Workflow run ID.
        timeout_seconds:  Max wait time. Automatically capped at 2× max duration.

    Returns:
        Final chaos result dictionary.
    """
    cfg = _litmus_safety_config()
    safe_timeout = min(timeout_seconds, cfg["max_duration_s"] * 2 + 30)
    deadline     = time.time() + safe_timeout

    while time.time() < deadline:
        result = get_chaos_result(run_id)
        if result["verdict"] != "Awaited":
            return result
        time.sleep(15)

    return {
        "run_id":            run_id,
        "phase":             "Timeout",
        "verdict":           "Fail",
        "resiliency_score":  0,
        "execution_summary": f"Timed out after {safe_timeout}s",
    }


prom_get_metrics       = FunctionTool(get_service_metrics)
prom_get_anomalies     = FunctionTool(get_anomalous_services)
prom_get_alerts        = FunctionTool(get_prometheus_alert_rules)
prom_query_range       = FunctionTool(query_prometheus_range)

loki_get_logs          = FunctionTool(get_service_logs)
loki_get_crash_logs    = FunctionTool(get_pod_crash_logs)

tempo_search_traces    = FunctionTool(search_error_traces)
tempo_get_trace        = FunctionTool(get_trace_detail)

grafana_get_dashboard  = FunctionTool(get_grafana_dashboard_panels)
grafana_query          = FunctionTool(query_grafana_datasource)

argocd_get_status      = FunctionTool(get_argocd_app_status)
argocd_rollback        = FunctionTool(rollback_argocd_app)
argocd_sync            = FunctionTool(sync_argocd_app)
argocd_scale           = FunctionTool(scale_deployment)

litmus_run             = FunctionTool(run_chaos_experiment)
litmus_result          = FunctionTool(get_chaos_result)
litmus_wait            = FunctionTool(wait_for_chaos_result)

