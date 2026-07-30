import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

_configured_llm_providers = [
    name for name, env_var in [
        ("Groq", "GROQ_API_KEY"),
        ("Gemini", "GEMINI_API_KEY"),
        ("OpenAI", "OPENAI_API_KEY"),
    ] if os.getenv(env_var)
]
if _configured_llm_providers:
    print(f"[startup] LLM providers configured (priority order): {' -> '.join(_configured_llm_providers)}. "
          f"Coaching pipeline will use the LLM, with automatic failover between providers.")
else:
    print("[startup] No LLM provider API keys found (GROQ_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY) — "
          "coaching pipeline will use built-in mock responses. Check that a .env file with at least one "
          "of these keys exists in the directory you're running the server from.")

from backend.database import (
    create_conversation,
    add_message,
    get_conversation,
    save_analysis,
    save_report,
    get_report,
    get_all_reports,
    get_all_conversations
)
from backend.simulator import CustomerSimulator
from backend.agents import agent_orchestrator
from backend.replay_data import REPLAY_TRANSCRIPTS
from backend.rag import rag_engine

app = FastAPI(title="AI Customer Support Coaching Assistant Backend")

# Setup CORS for development.
# NOTE: allow_origins=["*"] combined with allow_credentials=True is invalid —
# browsers reject wildcard origins whenever credentials are allowed.
#
# Vite doesn't always run on 5173 (it auto-picks the next free port if that
# one's taken), so rather than hardcode a port we allow any localhost/
# 127.0.0.1 origin on any port for local dev via regex. For a real deployment,
# set FRONTEND_ORIGINS (comma-separated) to your actual domain(s) — those are
# matched exactly, not via the regex.
_extra_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active simulator instances per session
simulators: Dict[str, CustomerSimulator] = {}

class SessionCreateRequest(BaseModel):
    mode: str  # "Simulator", "Manual", "Replay"
    scenario: str
    personality: str

class ReportResponse(BaseModel):
    title: str
    resolution_quality_score: int
    sentiment_journey: List[str]
    competencies: Dict[str, int]
    conversation_summary: str
    recommendations: List[str]

class KBAddRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "General"
    tags: Optional[List[str]] = []

@app.get("/api/replays")
def list_replays():
    """List the pre-loaded replay transcripts available."""
    return [
        {"id": key, "title": val["title"], "scenario": val["scenario"], "personality": val["personality"]}
        for key, val in REPLAY_TRANSCRIPTS.items()
    ]

@app.post("/api/sessions/create")
def start_session(req: SessionCreateRequest):
    """Initializes a coaching session and database entry."""
    conv_id = create_conversation(req.mode, req.scenario, req.personality)
    
    # If in Simulator mode, initialize the CustomerSimulator
    if req.mode == "Simulator":
        simulators[conv_id] = CustomerSimulator(req.scenario, req.personality)
        
    return {"session_id": conv_id, "mode": req.mode, "scenario": req.scenario, "personality": req.personality}

@app.post("/api/sessions/{session_id}/report", response_model=ReportResponse)
def generate_session_report(session_id: str):
    """Concludes session, runs final orchestrator analysis, and returns structured report."""
    conv = get_conversation(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Generate and save report
    report = agent_orchestrator.generate_final_report(conv["messages"], conv["analysis_history"])
    save_report(session_id, report)
    return report

@app.get("/api/sessions/{session_id}/report", response_model=ReportResponse)
def fetch_session_report(session_id: str):
    """Retrieves an already generated report."""
    report = get_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return report

@app.get("/api/analytics")
def get_analytics():
    all_reps = get_all_reports()
    all_convs = get_all_conversations()
    
    total_sessions = len(all_reps)
    if total_sessions == 0:
        return {
            "total_sessions": 0,
            "avg_quality_score": 0,
            "escalation_rate": 0,
            "common_triggers": {},
            "knowledge_gaps": [],
            "improvement_trend": [],
            "historical_sessions": []
        }
        
    avg_score = int(sum(r["resolution_quality_score"] for r in all_reps.values()) / total_sessions)
    
    # Check escalation rate (sessions that hit "High" risk at any point)
    escalations_count = 0
    common_triggers = {}
    
    for cid, conv in all_convs.items():
        if cid not in all_reps:
            continue
            
        # Check if high risk occurred
        had_escalation = False
        for analysis in conv.get("analysis_history", []):
            if analysis.get("escalation_risk") == "High":
                had_escalation = True
                break
                
        # Fallback check based on final score
        if not had_escalation and all_reps[cid]["resolution_quality_score"] < 75:
            had_escalation = True
            
        if had_escalation:
            escalations_count += 1
            scenario = conv.get("scenario", "Unknown")
            common_triggers[scenario] = common_triggers.get(scenario, 0) + 1
            
    escalation_rate = int((escalations_count / total_sessions) * 100)
    
    # Analyze knowledge gaps
    gap_analysis = []
    scen_scores = {}
    for cid, conv in all_convs.items():
        if cid not in all_reps:
            continue
        scen = conv.get("scenario", "General")
        score = all_reps[cid]["resolution_quality_score"]
        if scen not in scen_scores:
            scen_scores[scen] = []
        scen_scores[scen].append(score)
        
    for scen, scores in scen_scores.items():
        avg_scen_score = sum(scores) / len(scores)
        if avg_scen_score < 85:
            gap_analysis.append({
                "topic": scen,
                "avg_score": int(avg_scen_score),
                "remedy": f"Review coaching articles for '{scen}' scenario and increase empathy checks."
            })
            
    if not gap_analysis:
        gap_analysis.append({
            "topic": "Billing Exceptions",
            "avg_score": 82,
            "remedy": "Add knowledge base articles detailing policy exceptions for subscription renewals."
        })
        
    # Improvement trend (scores over time) and historical sessions
    improvement_trend = []
    historical_sessions = []
    for cid, r in all_reps.items():
        conv = all_convs.get(cid, {})
        improvement_trend.append(r["resolution_quality_score"])
        historical_sessions.append({
            "session_id": cid,
            "title": r["title"],
            "resolution_quality_score": r["resolution_quality_score"],
            "scenario": conv.get("scenario", "General"),
            "mode": conv.get("mode", "Simulator")
        })
        
    return {
        "total_sessions": total_sessions,
        "avg_quality_score": avg_score,
        "escalation_rate": escalation_rate,
        "common_triggers": common_triggers if common_triggers else {"Billing Dispute": 1},
        "knowledge_gaps": gap_analysis,
        "improvement_trend": improvement_trend,
        "historical_sessions": historical_sessions
    }

def _preload_mock_analytics():
    # Session 1
    c1 = create_conversation("Simulator", "Billing Dispute", "Impatient")
    add_message(c1, "customer", "I have two charges of $29.99 on July 10th. I need you to refund one right now.")
    add_message(c1, "agent", "Hello, I apologize for the duplicate charge. I see the charge and will initiate a refund.")
    rep1 = {
        "title": "Billing Refund - Impatient Client Review",
        "resolution_quality_score": 82,
        "sentiment_journey": ["Angry", "Frustrated", "Neutral"],
        "competencies": {"empathy": 75, "clarity": 90, "policy_compliance": 100, "speed": 95},
        "conversation_summary": "Customer disputed double charge. Refund processed inside 2 turns with speed, though agent could have offered slightly more empathy upfront.",
        "recommendations": ["Acknowledge card balance impact before processing refund.", "Verify billing address for standard policy compliance."]
    }
    save_report(c1, rep1)
    
    # Session 2
    c2 = create_conversation("Replay", "Technical Issue", "Confused")
    add_message(c2, "customer", "My internet is down and router is flashing red. I have a meeting in 10 minutes.")
    add_message(c2, "agent", "I'm sorry to hear that. Let's perform a factory reset. Hold the pinhole reset button for 15 seconds.")
    rep2 = {
        "title": "Aura Router Setup - Confused Client Review",
        "resolution_quality_score": 92,
        "sentiment_journey": ["Frustrated", "Neutral", "Satisfied"],
        "competencies": {"empathy": 90, "clarity": 85, "policy_compliance": 95, "speed": 80},
        "conversation_summary": "Customer guided through factory reset steps to resolve outage. Connection restored, customer successfully joined meeting.",
        "recommendations": ["Great job validating customer urgency.", "Provide default Wi-Fi password reminders after factory resets."]
    }
    save_report(c2, rep2)

_preload_mock_analytics()


# ============================================================
# Knowledge Base Management Endpoints
# ============================================================

@app.get("/api/knowledge")
def list_knowledge_base():
    """Return all documents in the knowledge base, plus which retrieval mode is active."""
    docs = rag_engine.get_all_documents()
    return {
        "total": len(docs),
        "documents": docs,
        "retrieval_mode": "vector (chromadb + embeddings)" if rag_engine.vector_enabled else "tf-idf (fallback)",
    }


@app.post("/api/knowledge/add")
def add_knowledge_entry(req: KBAddRequest):
    """
    Add a plain-text FAQ / support article to the knowledge base.
    Accepts JSON with title, content, category, and optional tags.
    """
    try:
        doc = rag_engine.add_document(
            title=req.title,
            content=req.content,
            category=req.category or "General",
            tags=req.tags or [],
            source="user-faq",
        )
        return {"success": True, "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/knowledge/upload-file")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    category: str = Form(default="Uploaded Document"),
    tags: str = Form(default=""),
):
    """
    Upload a file (PDF, TXT, DOCX, MD, CSV) and ingest its text into the knowledge base.
    `tags` should be a comma-separated string.
    """
    MAX_SIZE_MB = 10
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_SIZE_MB} MB.")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        docs = rag_engine.ingest_file(
            filename=file.filename or "upload",
            file_bytes=file_bytes,
            category=category,
            tags=tag_list,
        )
        return {"success": True, "chunks_created": len(docs), "documents": docs}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/knowledge/{doc_id}")
def delete_knowledge_entry(doc_id: str):
    """Remove a user-added document from the knowledge base by its ID."""
    removed = rag_engine.remove_document(doc_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail="Document not found or is a protected built-in entry that cannot be deleted."
        )
    return {"success": True, "removed_id": doc_id}


@app.websocket("/ws/coaching/{session_id}")
async def ws_coaching_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint handling real-time turn exchange and coaching triggers.
    """
    await websocket.accept()
    
    # Fetch session details
    conv = get_conversation(session_id)
    if not conv:
        await websocket.close(code=4004, reason="Session not found")
        return
        
    mode = conv["mode"]
    scenario = conv["scenario"]
    personality = conv["personality"]

    # Replay variables
    replay_index = 0
    replay_turns = []
    if mode == "Replay":
        # Find matches for transcripts
        matching_replay = None
        for key, val in REPLAY_TRANSCRIPTS.items():
            if val["scenario"] == scenario:
                matching_replay = val
                break
        # Fallback to standard
        if not matching_replay:
            matching_replay = list(REPLAY_TRANSCRIPTS.values())[0]
        replay_turns = matching_replay["turns"]

    try:
        while True:
            # Receive text frame
            data = await websocket.receive_text()
            event = json.loads(data)
            action = event.get("action")

            if action == "start":
                # Initial message delivery trigger
                if mode == "Simulator":
                    # Simulator starts by speaking first
                    sim = simulators.get(session_id)
                    if sim:
                        cust_msg = sim.get_next_customer_message()
                        msg = add_message(session_id, "customer", cust_msg)
                        
                        # Run coaching analysis on this first turn
                        analysis = agent_orchestrator.run_pipeline(conv["messages"], cust_msg)
                        save_analysis(session_id, analysis)
                        
                        # Emit to client
                        await websocket.send_json({
                            "type": "turn",
                            "message": msg,
                            "analysis": analysis
                        })
                elif mode == "Replay":
                    # Replay starts empty or we load first turn
                    pass
                elif mode == "Manual":
                    # Manual mode waits for the user to input a customer message
                    pass

            elif action == "agent_message":
                text = event.get("text", "")
                if not text:
                    continue
                    
                # 1. Add agent message to history
                agent_msg = add_message(session_id, "agent", text)
                
                # 2. Get last customer message for reference (to grade agent response)
                cust_msgs = [m for m in conv["messages"] if m["sender"] == "customer"]
                last_cust_text = cust_msgs[-1]["text"] if cust_msgs else ""
                
                # 3. Grade the agent's message
                analysis = agent_orchestrator.run_pipeline(
                    conv["messages"],
                    last_cust_text,
                    agent_last_reply=text
                )
                save_analysis(session_id, analysis)
                
                # Send the update to agent dashboard (grades and updates)
                await websocket.send_json({
                    "type": "agent_grade",
                    "message": agent_msg,
                    "analysis": analysis
                })
                
                # 4. If simulator mode, generate the next customer response
                if mode == "Simulator":
                    sim = simulators.get(session_id)
                    if sim:
                        # Wait a short beat to simulate thinking
                        cust_msg = sim.get_next_customer_message(agent_response=text)
                        cust_msg_db = add_message(session_id, "customer", cust_msg)
                        
                        # Run pipeline on customer message to get new tips/suggestions
                        analysis_cust = agent_orchestrator.run_pipeline(conv["messages"], cust_msg)
                        save_analysis(session_id, analysis_cust)
                        
                        await websocket.send_json({
                            "type": "turn",
                            "message": cust_msg_db,
                            "analysis": analysis_cust
                        })

            elif action == "customer_message":
                # Used in Manual mode to input customer text
                text = event.get("text", "")
                if not text:
                    continue
                    
                cust_msg = add_message(session_id, "customer", text)
                
                # Run pipeline
                analysis = agent_orchestrator.run_pipeline(conv["messages"], text)
                save_analysis(session_id, analysis)
                
                await websocket.send_json({
                    "type": "turn",
                    "message": cust_msg,
                    "analysis": analysis
                })

            elif action == "replay_next":
                # Used in Replay mode to advance conversation
                if replay_index < len(replay_turns):
                    turn = replay_turns[replay_index]
                    replay_index += 1
                    
                    msg = add_message(session_id, turn["sender"], turn["text"])
                    
                    # Run analysis
                    if turn["sender"] == "customer":
                        analysis = agent_orchestrator.run_pipeline(conv["messages"], turn["text"])
                    else:
                        # Find last customer message
                        cust_msgs = [m for m in conv["messages"] if m["sender"] == "customer"]
                        last_cust_text = cust_msgs[-1]["text"] if cust_msgs else ""
                        analysis = agent_orchestrator.run_pipeline(
                            conv["messages"], 
                            last_cust_text, 
                            agent_last_reply=turn["text"]
                        )
                        
                    save_analysis(session_id, analysis)
                    
                    await websocket.send_json({
                        "type": "replay_turn",
                        "message": msg,
                        "analysis": analysis,
                        "has_more": replay_index < len(replay_turns)
                    })

    except WebSocketDisconnect:
        # Cleanup simulator if active
        if session_id in simulators:
            del simulators[session_id]
        print(f"Client disconnected from WebSocket session {session_id}")
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
        # Cleanup
        if session_id in simulators:
            del simulators[session_id]

# Optional: Mount frontend static build directory if serving built SPA
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")