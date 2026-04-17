# 🚀 Self-Healing Cloud (Agentic AI for Kubernetes)

## 👥 Team Name

HackToFuture4.0 – Team <INVOX>

---

## 🧠 Problem Statement

Managing Kubernetes systems is complex and reactive.
When failures occur (crashes, latency spikes, errors), engineers must manually:

* Monitor metrics
* Identify root causes
* Apply fixes
* Validate system stability

This process is slow, error-prone, and not scalable.

---

## 💡 Our Solution

We built a **Self-Healing Cloud System** powered by **Agentic AI** that can:

👉 Detect issues
👉 Automatically fix them
👉 Validate system stability

All without human intervention.

The system uses a **3-agent architecture**:

1. **Monitor Agent** → Detects anomalies using Prometheus
2. **Heal Agent** → Fixes issues using ArgoCD
3. **Validation Agent** → Tests resilience using LitmusChaos

This creates a fully automated **Monitor → Heal → Validate** pipeline.

---

## 🧠 Architecture Overview

```
Prometheus / Loki / Grafana
            ↓
     🤖 AI Agents (Google ADK)
   ┌───────────────┐
   │ Monitor Agent │
   └──────┬────────┘
          ↓
   ┌───────────────┐
   │ Heal Agent    │
   └──────┬────────┘
          ↓
   ┌───────────────┐
   │ Validation    │
   │ Agent         │
   └───────────────┘
            ↓
   ArgoCD + LitmusChaos
```

---

## 🔑 Key Features

* 🤖 **Agentic AI Workflow** (3 autonomous agents)
* 📊 **Real-time anomaly detection** using Prometheus
* 🔁 **Auto-remediation** via ArgoCD (rollback/sync)
* 🧪 **Chaos validation** using LitmusChaos
* ⚡ **Quota-aware LLM system** (handles API limits intelligently)
* 📡 **Streaming + API-based monitoring**
* 🧠 Smart decision-making using Gemini models

---

## 🛠️ Tech Stack

* **Backend:** FastAPI 
* **AI Framework:** Google ADK (Agent Development Kit) 
* **LLM:** Gemini (gemini-flash-latest)
* **Monitoring:** Prometheus
* **Logging:** Loki
* **Visualization:** Grafana
* **Deployment:** ArgoCD
* **Chaos Testing:** LitmusChaos
* **Language:** Python

---

## ⚙️ How It Works

1. Monitor Agent scans cluster using Prometheus
2. If anomalies found → classify severity
3. Heal Agent performs:

   * 🔄 Rollback
   * 🔁 Sync
4. Validation Agent:

   * Injects chaos
   * Verifies resilience

System automatically stops if cluster is healthy → saves API quota 

---

## ⚙️ How to Run

```bash
# Clone repo
git clone https://github.com/<your-team>/hacktofuture4-<team_id>.git

cd project

# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
```

Server runs on:

```
http://localhost:8000
```

---

## 🔌 API Endpoints

* `GET /health` → System status
* `POST /trigger` → Run full healing workflow
* `GET /logs` → Workflow history
* `POST /agent/query` → Query specific agent
* `POST /metrics/query` → Direct Prometheus query (no LLM usage)
* `POST /chaos/inject` → Inject failure

---

## ⚡ Smart Optimization

* ⏱️ Rate-limited LLM calls (4s gap)
* 🔁 Retry + circuit breaker for API limits
* 📉 Minimizes LLM usage (max ~6 calls/workflow)
* 💡 Uses tools instead of LLM where possible

This ensures smooth operation even on **free-tier APIs** 

---

## 🚀 Future Improvements

* 🌐 Frontend dashboard (real-time visualization)
* ☁️ Cloud deployment (AWS/GCP)
* 📈 Predictive failure detection
* 🤖 Multi-cluster support
* 🔐 RBAC + production safety layers

---

## 🏁 Conclusion

This project demonstrates how **Agentic AI can transform DevOps**
from reactive monitoring → to **fully autonomous self-healing systems**.

---

