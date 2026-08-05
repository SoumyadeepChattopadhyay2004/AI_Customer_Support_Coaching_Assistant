<div align="center">

# 🎧 AI Customer Support Coaching Assistant

**A real-time, multi-agent AI coaching platform that listens to support conversations as they happen — and makes every agent better, one turn at a time.**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?logo=langchain&logoColor=white)](https://python.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Search-FF6F61)](https://www.trychroma.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?logo=react&logoColor=white)](https://vitejs.dev/)
[![WebSockets](https://img.shields.io/badge/Realtime-WebSockets-4B32C3)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

*Analyze intent. Detect sentiment. Retrieve the right knowledge. Coach the reply. Catch escalation before it happens.*

</div>

---

## 📖 Overview

**AI Customer Support Coaching Assistant** is a generative-AI coaching layer that sits alongside a live customer support conversation. Instead of grading agents after the fact, it works **turn-by-turn, in real time**: reading every customer message, understanding what's really being asked, pulling the exact policy or troubleshooting article that applies, and handing the human agent ready-to-send response suggestions — while simultaneously watching the whole conversation for signs it's about to go wrong.

At the end of a session, it produces a structured performance report — sentiment journey, competency scores, and personalized recommendations — so supervisors can coach agents with evidence instead of guesswork.

It's built to run with **zero API keys** out of the box (deterministic rule-based mock mode), and to seamlessly upgrade to full LLM-powered reasoning the moment you add a free-tier key from Groq, Gemini, or OpenAI.

---

## ✨ Key Features

### 🧠 Multi-Agent Coaching Pipeline
Four specialist agents, orchestrated as a LangChain **LCEL** graph — not a straight-line script:

| Agent | Responsibility |
|---|---|
| 🔍 **Customer Understanding Agent** | Extracts intent, sentiment (`Angry` / `Frustrated` / `Neutral` / `Satisfied`), tone, and entities (emails, order numbers, amounts) from the customer's message |
| 📚 **Knowledge Recommendation Agent** | Runs a RAG lookup over the support knowledge base and returns the most relevant policy/troubleshooting snippets |
| 💬 **Response Coaching Agent** | Drafts multiple distinct reply suggestions, gives actionable coaching tips, and grades the agent's last reply (empathy & clarity scores) |
| 🚨 **Quality Monitoring Agent** | Continuously assesses escalation risk, recommends intervention strategies, and scores resolution quality |

The pipeline runs `understand → retrieve → { coach ∥ monitor } → merge`, with the Coaching and Quality Monitoring agents executing **concurrently** since neither depends on the other's output — a real orchestration win, not just clean code.

### 🔁 Automatic Multi-Provider LLM Failover
No single point of failure, no paid API required to get started:

```
Groq (fastest, free tier)  →  Gemini (generous free quota)  →  OpenAI (fallback)
```

Powered by LangChain's native `.with_fallbacks()` — if one provider errors or rate-limits, the next configured provider picks up the very next call automatically. Every response tells you whether it came from an LLM or the deterministic mock engine (`ai_generated` flag), so nothing is a black box.

### 📚 Hybrid RAG Knowledge Base
- **Vector search** via ChromaDB with a local ONNX embedding model — no GPU, no external embedding API key required.
- **Automatic TF-IDF fallback** — if the embedding model can't be downloaded (offline/firewalled), the system transparently degrades to a pure-Python TF-IDF matcher with zero crashes.
- **Upload your own knowledge**: ingest PDF, DOCX, TXT, MD, or CSV files directly through the API — text is extracted, chunked, and embedded automatically.
- Pre-loaded with built-in articles covering billing disputes, technical troubleshooting, cancellations, password resets, and shipping — fully extensible via the API.

### 🎮 Three Ways to Train
| Mode | Description |
|---|---|
| **Simulator** | An AI-driven virtual customer (4 personalities: Angry, Confused, Impatient, Polite) converses live with the trainee over WebSocket |
| **Manual** | Paste in or type real customer messages and get instant coaching on your responses |
| **Replay** | Step through pre-built historical transcripts (billing disputes, router troubleshooting, cancellation saves) to study exemplar interactions |

### 📊 Analytics Dashboard
Aggregate reporting across every session: average quality score, escalation rate, common escalation triggers, identified knowledge gaps, and an improvement trend over time.

### ⚡ Real-Time WebSocket Architecture
Every customer message and every agent reply is analyzed and streamed back over a single persistent WebSocket connection (`/ws/coaching/{session_id}`) — coaching suggestions arrive as the conversation happens, not after.

---

## 🏗️ Architecture

<div align="center">

![Architecture Diagram](https://raw.githubusercontent.com/SoumyadeepChattopadhyay2004/AI_Customer_Support_Coaching_Assistant/main/architecture.png)

</div>

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI + Uvicorn (WebSockets, REST) |
| **Agent Orchestration** | LangChain Core (LCEL: `Runnable`, `RunnableLambda`, `RunnablePassthrough`) |
| **LLM Providers** | Groq, Google Gemini, OpenAI — all via OpenAI-compatible endpoints (`langchain-openai`) |
| **Vector Store** | ChromaDB with local ONNX embeddings (+ pure-Python TF-IDF fallback) |
| **Document Parsing** | `pypdf`, `python-docx` |
| **Data Validation** | Pydantic |
| **Frontend** | React + Vite |
| **Storage** | In-memory session store (swappable for a persistent DB) |

---

## 📁 Project Structure

```
AI_Customer_Support_Coaching_Assistant/
├── backend/
│   ├── main.py                    # FastAPI app, REST routes, WebSocket handler
│   ├── agents.py                  # 4 specialist agents + LCEL orchestrator + LLM client
│   ├── rag.py                     # Knowledge base, vector/TF-IDF retrieval, file ingestion
│   ├── simulator.py                # AI-driven customer simulator (LLM + mock fallback)
│   ├── database.py                # In-memory conversation/report store
│   ├── replay_data.py             # Pre-built replay transcripts
│   ├── test_agents.py             # End-to-end pipeline smoke test
│   ├── test_agents_individual.py  # Per-agent inspection/debugging tool
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   └── ...                        # React + Vite coaching console
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.13+**
- **Node.js 18+** and npm
- (Optional) A free API key from [Groq](https://console.groq.com/keys), [Google AI Studio](https://aistudio.google.com), or [OpenAI](https://platform.openai.com/api-keys) for full LLM-powered coaching — the app runs perfectly well in deterministic mock mode without one.

### 1. Clone the repository
```bash
git clone https://github.com/SoumyadeepChattopadhyay2004/AI_Customer_Support_Coaching_Assistant.git
cd AI_Customer_Support_Coaching_Assistant
```

### 2. Backend setup
```bash
cd backend
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Create your `.env` file from the example and add at least one provider key (optional):
```bash
cp .env.example .env   # Windows: copy .env.example .env
```

```env
# --- OPTION 1: Groq (Free ~100k tokens/day, fastest) ---
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# --- OPTION 2: Google Gemini (Free 1M tokens/day) ---
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

# --- OPTION 3: OpenAI ---
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

Run the backend:
```bash
uvicorn main:app --reload --port 8000
```
The API is now live at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`).

### 3. Frontend setup
```bash
cd frontend
npm install
npm run dev
```
The coaching console will be available at the port Vite prints (typically `http://localhost:5173`). The backend automatically allows any `localhost`/`127.0.0.1` origin in development — no extra CORS config needed.

### 4. (Optional) Production build
```bash
cd frontend
npm run build
```
If a `frontend/dist` folder exists, the FastAPI backend will automatically serve it as a static SPA — one process, one deployment.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/sessions/create` | Start a new coaching session (`Simulator` / `Manual` / `Replay`) |
| `GET` | `/api/replays` | List available pre-built replay transcripts |
| `WS` | `/ws/coaching/{session_id}` | Real-time coaching stream — send/receive turns and analysis |
| `POST` | `/api/sessions/{session_id}/report` | Generate the final structured performance report |
| `GET` | `/api/sessions/{session_id}/report` | Fetch an already-generated report |
| `GET` | `/api/analytics` | Aggregate analytics across all sessions |
| `GET` | `/api/knowledge` | List all knowledge base documents |
| `POST` | `/api/knowledge/add` | Add a plain-text FAQ/article |
| `POST` | `/api/knowledge/upload-file` | Upload & ingest a PDF/DOCX/TXT/MD/CSV file |
| `DELETE` | `/api/knowledge/{doc_id}` | Remove a user-added knowledge entry |

**WebSocket actions:** `start`, `agent_message`, `customer_message`, `replay_next` — see [`main.py`](./backend/main.py) for the full event contract.

---

## 🧪 Testing

```bash
cd backend

# End-to-end pipeline smoke test
python test_agents.py

# Inspect a single agent's output in isolation
python test_agents_individual.py understanding
python test_agents_individual.py knowledge
python test_agents_individual.py coaching
python test_agents_individual.py quality

# Or run all four in sequence
python test_agents_individual.py
```

---

## 🗺️ Roadmap

- [ ] Persistent database backend (PostgreSQL/MongoDB) to replace in-memory storage
- [ ] User authentication & role-based supervisor dashboards
- [ ] Voice/speech-to-text input for live call coaching
- [ ] Multi-language support
- [ ] Exportable PDF performance reports

---

## 🤝 Contributing

Contributions are welcome! To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m "Add amazing feature"`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

<div align="center">

**Built with ❤️ by [Soumyadeep Chattopadhyay](https://github.com/SoumyadeepChattopadhyay2004)**

⭐ If this project helped you, consider giving it a star!

</div>
