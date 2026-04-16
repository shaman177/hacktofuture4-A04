"""
agents.py — The Brains
Google ADK agents optimised for the Gemini free tier.

FREE TIER LIMITS (as of April 2026):
  gemini-2.0-flash            : 15 RPM  · 1 000 000 TPD  · 1 500 req/day
  gemini-2.5-flash            : 10 RPM  · 250 000 TPD    · 20  req/day   ← DO NOT USE
  gemini-2.5-flash-lite       : 30 RPM  · 1 000 000 TPD  · 1 500 req/day ← BEST

DESIGN PRINCIPLES FOR FREE TIER:
  1. Use gemini-2.5-flash-lite — it has 30 RPM (2× more than 2.0-flash) on free tier.
  2. Each agent makes at most 2 LLM calls per workflow run (initial + one tool loop).
  3. Tools do the heavy lifting — agents interpret, not gather.
  4. Instructions are short: less prompt = fewer input tokens = stays under TPD limit.
  5. Monitor agent does ONE Prometheus call and decides from that alone.
     Loki/Tempo calls only happen when Prometheus already confirmed a problem.
"""

from google.adk.agents import Agent

from tools import (
    prom_get_anomalies,
    prom_get_metrics,
    prom_get_alerts,
    loki_get_logs,
    loki_get_crash_logs,
    tempo_search_traces,
    grafana_query,
    argocd_get_status,
    argocd_rollback,
    argocd_sync,
    litmus_run,
    litmus_result,
    litmus_wait,
)

GEMINI_MODEL = "gemini-3.1-flash-lite-preview"




monitor_agent = Agent(
    name="monitor_agent",
    model=GEMINI_MODEL,
    description="Scans cluster health via Prometheus. Escalates to Loki only if anomalies found.",
    instruction="""
You are an SRE monitoring a Kubernetes cluster.

STEP 1: Call get_anomalous_services. If it returns total_anomalous=0, stop immediately and return the healthy JSON below — do NOT call any other tool.

STEP 2: Scan for parallel failures. If multiple services or pods show near-identical restart timestamps (via get_pod_crash_logs) or simultaneous 'Down' statuses, flag this as a 'Synchronous Deletion' event and escalate for immediate GitOps remediation.

STEP 3: Only if anomalies exist — for each anomalous service, call get_service_metrics.
  If error_rate > 10% or p99 > 2000ms also call get_service_logs (level="error") for that service only.
  Do NOT call tempo, trace, or alert tools — save API quota.

CLASSIFICATION:
  CRITICAL: error_rate > 10% OR p99_latency > 2000ms
  DEGRADED:  error_rate 2-10% OR p99_latency 500-2000ms

ROOT CAUSE (from log patterns only):
  CrashLoopBackOff       → ROLLBACK
  Synchronous Deletion   → ROLLBACK
  timeout/connection     → SYNC
  no clear pattern       → ROLLBACK

Return ONLY valid JSON, no extra text:
{
  "anomalies_found": true | false,
  "services": [
    {
      "service": "<name>",
      "namespace": "default",
      "severity": "CRITICAL | DEGRADED",
      "error_rate_pct": 0.0,
      "p99_latency_ms": 0.0,
      "likely_cause": "<one sentence>",
      "recommended_action": "ROLLBACK | SYNC"
    }
  ],
  "summary": "<one sentence>"
}
""",
    tools=[
        prom_get_anomalies,
        prom_get_metrics,
        loki_get_logs,
        loki_get_crash_logs,
    ],
)



heal_agent = Agent(
    name="heal_agent",
    model=GEMINI_MODEL,
    description="Diagnoses root cause and remediates via ArgoCD. One action per service.",
    instruction="""
You are an SRE. You receive JSON from monitor_agent listing anomalous services.

For each service:
1. Remediate simultaneous pod failures by calling get_argocd_app_status to identify recent state changes.
2. If a sync recently occurred (sync_status is 'OutOfSync' or health is 'Progressing'), execute rollback_argocd_app to revert the breaking change.
3. Otherwise, inspect loki_get_crash_logs for OOMKilled errors.
4. If OOMKilled or unknown, attempt a final sync_argocd_app as a last resort.

Action mapping if recommended_action is provided:
   - ROLLBACK → rollback_argocd_app(app_name)
   - SYNC     → sync_argocd_app(app_name)

Return ONLY valid JSON, no extra text:
{
  "remediations": [
    {
      "service": "<name>",
      "namespace": "<ns>",
      "root_cause": "<diagnosis>",
      "action_taken": "ROLLBACK | SYNC",
      "action_detail": "<revision>",
      "success": true | false,
      "confidence": "HIGH | MEDIUM | LOW"
    }
  ],
  "summary": "<one sentence>"
}
""",
    tools=[
        prom_get_metrics,
        argocd_get_status,
        argocd_rollback,
        argocd_sync,
    ],
)



validation_agent = Agent(
    name="validation_agent",
    model=GEMINI_MODEL,
    description="Validates healed services with LitmusChaos. Safety gates are automatic.",
    instruction="""
You are a chaos engineer. You receive JSON from heal_agent.

For each service where success=true:
1. Call run_chaos_experiment:
   - experiment_name: "<service>-val"
   - target_namespace: namespace from heal_agent (skip if namespace not in allowed list — the tool handles this)
   - target_app: service name
   - chaos_type: "pod-delete" (always use pod-delete — safest, works for all cases)
2. Call wait_for_chaos_result with the run_id.

If run_chaos_experiment returns skipped=true, mark verdict as SKIPPED — this is fine.
Skip validation entirely for services where success=false.

Return ONLY valid JSON, no extra text:
{
  "validations": [
    {
      "service": "<name>",
      "chaos_type": "pod-delete",
      "skipped": false,
      "skip_reason": null,
      "resiliency_score": 0,
      "verdict": "PASS | FAIL | SKIPPED",
      "recommendation": "Stable | <next step>"
    }
  ],
  "overall_status": "ALL_PASS | PARTIAL_PASS | ALL_FAIL | ALL_SKIPPED",
  "escalate": false,
  "escalation_reason": null,
  "summary": "<one sentence>"
}
""",
    tools=[
        litmus_run,
        litmus_wait,
    ],
)



insight_agent = Agent(
    name="insight_agent",
    model=GEMINI_MODEL,
    description="Answers ad-hoc observability questions via Prometheus and Grafana.",
    instruction="""
You are an observability analyst.
Answer the user's question using get_service_metrics or query_grafana_datasource.
Use ONE tool call maximum. Return a concise natural-language answer with key numbers.
""",
    tools=[
        prom_get_metrics,
        prom_get_anomalies,
        grafana_query,
    ],
)


AGENTS = {
    "monitor":    monitor_agent,
    "heal":       heal_agent,
    "validation": validation_agent,
    "insight":    insight_agent,
}
