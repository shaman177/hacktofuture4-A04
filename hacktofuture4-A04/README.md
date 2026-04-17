# 🌌 Antigravity: Self-Healing Cloud AI
### 🚀 Team: INVOX | HackToFuture 4

[![Gemini](https://img.shields.io/badge/Powered%20By-Gemini%203.1%20Flash--Lite-blue?style=for-the-badge&logo=google-gemini)](https://deepmind.google/technologies/gemini/)
[![Kubernetes](https://img.shields.io/badge/Tech-Kubernetes-blue?style=for-the-badge&logo=kubernetes)](https://kubernetes.io/)
[![ArgoCD](https://img.shields.io/badge/Ops-ArgoCD-orange?style=for-the-badge&logo=argo)](https://argoproj.github.io/cd/)

---

## ⚡ Problem Statement
In modern cloud architectures, **downtime is expensive.** Standard Site Reliability Engineering (SRE) relies on human intervention to diagnose and fix cluster failures, leading to a high **Mean Time To Recovery (MTTR)**. 

Specifically, subtle performance degradations (mild errors) and simultaneous parallel failures (Synchronous Deletions) are notoriously difficult for traditional monitoring tools to resolve without human experts.

## 🧠 The Solution
**Antigravity** is an autonomous agentic system powered by **Gemini 3.1 Flash-Lite** that acts as a 24/7 AI-SRE. 

It implements a circular "Autonomous Pulse" loop that consistently Monitors, Heals, and Validates your cluster health without human input:
1. **Monitor (Detection)**: Scans Prometheus metrics and Loki logs to identify anomalies (CrashLoops, Latency Spikes, Sync Errors).
2. **Heal (Remediation)**: Intelligent agents analyze root causes and execute automated **ArgoCD Rollbacks** or **Syncs**.
3. **Validate (Verification)**: Uses **LitmusChaos** to stress-test the fix, ensuring the system is truly resilient and not just temporarily patched.

---

## ✨ Core Features
- **Intelligent Mass Chaos (4x)**: A "Spray Chaos" engine that injects realistic "Mild Error Cocktails" (Latency, CPU throttling, Memory leaks) across multiple services simultaneously.
- **Parallel Failure Logic**: Sophisticated agent instructions for detecting "Synchronous Deletions"—mass failures caused by bad GitOps deployments.
- **Real-Time Storyboard**: A premium glassmorphism dashboard that visualizes the "internal brain" of the agents as they diagnose and repair the cluster.
- **Zero API Inflation**: Highly optimized agent loops that process multiple complex failures in a single LLM turn to save API quota.

---

## 🛠️ Tech Stack
| Component | Technology |
| :--- | :--- |
| **Brain** | Gemini 3.1 Flash-Lite (Google ADK) |
| **Observability** | Prometheus, Loki (Logs), Tempo (Traces), Grafana |
| **GitOps** | ArgoCD |
| **Chaos Eng.** | LitmusChaos |
| **Backend** | Python (FastAPI) |
| **Frontend** | Vanilla JS / CSS (Modern Glassmorphism) |

---

## ⚡ One-Click Execution (Windows)
We provide a convenience script to launch the full environment (Backend, Frontend, and Kubernetes Port-Forwards) in secondary terminal windows:
1. Run **`START_ALL.bat`** from the root directory.
2. The dashboard will automatically open at `http://localhost:3000`.

---

## 🛠️ How To Run (Step-by-Step)

### 🔹 1. Prerequisites
- **Python 3.10+**
- **Kubernetes Cluster** (local/remote) with Prometheus, ArgoCD, and LitmusChaos installed.
- **API Key**: A valid Gemini API Key.

### 🔹 2. Backend Setup
1. Open the `/backend-agents` directory.
2. Create a `.env` file from the template and add your API key:
   ```env
   GOOGLE_API_KEY=your_key_here
   ARGOCD_TOKEN=your_token_here
   PROMETHEUS_URL=http://localhost:9090
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend:
   ```bash
   python main.py
   ```

### 🔹 3. Frontend Setup
1. Open the `/frontend` directory.
2. Start a local server:
   ```bash
   python -m http.server 3000
   ```
3. Access the dashboard at **`http://localhost:3000`**.

---

## 📸 Dashboard Preview

![Dashboard Overview](https://raw.githubusercontent.com/shaman177/hacktofuture4-A04/main/visuals/dashboard_demo.png)

> **Note**: For the full "Mass Chaos" demo, navigate to the **Chaos & Heal** tab and click **🛰️ Spray Chaos (4x)**.

---
**TEAM INVOX** | Built for HackToFuture 4
