# Antigravity: Autonomous Self-Healing Cloud AI
### Team INVOX | HackToFuture 4

[![Gemini](https://img.shields.io/badge/Powered%20By-Gemini%203.1%20Flash--Lite-blue?style=flat-square&logo=google-gemini)](https://deepmind.google/technologies/gemini/)
[![Kubernetes](https://img.shields.io/badge/Infrastructure-Kubernetes-326ce5?style=flat-square&logo=kubernetes)](https://kubernetes.io/)
[![ArgoCD](https://img.shields.io/badge/GitOps-ArgoCD-ef7b4d?style=flat-square&logo=argo)](https://argoproj.github.io/cd/)

---

## Problem Statement
In modern cloud-native environments, **downtime directly impacts revenue.** Traditional Site Reliability Engineering (SRE) workflows rely heavily on manual intervention to diagnose complex failures, resulting in elevated **Mean Time To Recovery (MTTR)**. 

Subtle performance degradations ("Gray Failures") and large-scale parallel failures (Synchronous Deletions) often escape standard threshold-based alerting, requiring human experts to sift through logs and metrics to identify the root cause.

## Proposed Solution
**Antigravity** is an autonomous agentic framework powered by **Gemini 3.1 Flash-Lite** that serves as a 24/7 AI-driven SRE. 

The system implements a continuous "Autonomous Pulse" loop designed to **Monitor, Heal, and Validate** cluster health without human intervention:
1. **Monitor**: Probabilistic scanning of Prometheus metrics and Loki logs to detect anomalies such as CrashLoops, Latency Spikes, and Sync Errors.
2. **Heal**: Agentic reasoning models analyze diagnostic data to execute automated **ArgoCD Rollbacks** or configuration **Syncs** based on real-time root-cause analysis.
3. **Validate**: Integration with **LitmusChaos** to perform post-remediation stress tests, verifying that the system has returned to a resilient steady-state.

---

## Core Features
*   **Intelligent Mass Chaos (4x)**: A specialized engine that simulates complex multi-service failures (Latency, CPU throttling, and Memory leaks) to demonstrate the agent's parallel diagnostic capabilities.
*   **Parallel Failure Logic**: Advanced reasoning patterns for identifying "Synchronous Deletions"—mass failures typical of incorrect GitOps deployments or platform-wide outages.
*   **Agent Storyboard**: A high-fidelity dashboard visualizing the "internal chain-of-thought" of the agents as they navigate the detection-to-healing journey.
*   **Quota Optimization**: Highly efficient prompt engineering that batches multi-service diagnostics into single LLM turns, strictly adhering to API rate limits.

---

## Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Artificial Intelligence** | Gemini 3.1 Flash-Lite (Google ADK) |
| **Observability** | Prometheus, Loki, Tempo, Grafana |
| **Continuous Delivery** | ArgoCD (GitOps) |
| **Resilience Testing** | LitmusChaos |
| **Backend** | Fast API (Python) |
| **Frontend** | Modern Vanilla JS / CSS |

---

## Project Setup Instructions

### 1. Prerequisites
*   **Python 3.10+**
*   **Kubernetes Cluster** with Prometheus, ArgoCD, and LitmusChaos installed.
*   **Gemini API Key**: Required for autonomous reasoning.

### 2. Backend Installation
1. Navigate to the `backend-agents` directory.
2. Configure your environment in a `.env` file:
   ```env
   GOOGLE_API_KEY=your_gemini_key
   ARGOCD_TOKEN=your_argocd_token
   PROMETHEUS_URL=http://localhost:9090
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   python main.py
   ```

### 3. Frontend Installation
1. Navigate to the `frontend` directory.
2. Launch a local web server:
   ```bash
   python -m http.server 3000
   ```
3. Open the dashboard at `http://localhost:3000`.

---

## Dashboard Preview

![Dashboard Overview](https://raw.githubusercontent.com/shaman177/hacktofuture4-A04/main/visuals/dashboard_demo.png)

> **Deployment Note**: For a full system demonstration, use the **Spray Chaos (4x)** button in the Chaos Management tab to observe the parallel remediation workflow.

---
**TEAM INVOX** | HackToFuture 4
