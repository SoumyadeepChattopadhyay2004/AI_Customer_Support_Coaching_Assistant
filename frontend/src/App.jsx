import React, { useState, useEffect, useRef } from 'react';

const SCENARIOS = ["Billing Dispute", "Technical Issue", "Subscription Save"];
const PERSONALITIES = ["Angry", "Confused", "Impatient", "Polite"];

function App() {
  // Session Configuration State
  const [mode, setMode] = useState("Simulator");
  const [scenario, setScenario] = useState("Billing Dispute");
  const [personality, setPersonality] = useState("Angry");
  const [replayId, setReplayId] = useState("");
  const [replays, setReplays] = useState([]);
  
  // Active Connection / Session State
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState("");
  const [customerInputText, setCustomerInputText] = useState("");
  const [hasMoreReplay, setHasMoreReplay] = useState(true);
  
  // Real-Time Analytics State (Coaching Console)
  const [activeAnalysis, setActiveAnalysis] = useState({
    intent: "Waiting for message...",
    sentiment: "Neutral",
    tones: ["Neutral"],
    entities: { email: null, amount: null },
    retrieved_documents: [],
    suggestions: [],
    coaching_tips: [
      "Select a mode, scenario, and personality to start a support session.",
      "The coaching console will supply real-time recommendations as the chat develops."
    ],
    agent_evaluation: null,
    escalation_risk: "Low",
    escalation_reasoning: "No active risk indicators detected.",
    intervention_strategy: "N/A",
    resolution_quality_score: 100,
    conversation_summary: []
  });

  // Post-Interaction Report Modal State
  const [reportData, setReportData] = useState(null);
  const [showReport, setShowReport] = useState(false);

  // Performance Analytics Module State
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [analyticsData, setAnalyticsData] = useState(null);

  // Knowledge Base Manager State
  const [showKB, setShowKB] = useState(false);
  const [expandedRagDocs, setExpandedRagDocs] = useState({});
  const [kbDocuments, setKbDocuments] = useState([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbUploadLoading, setKbUploadLoading] = useState(false);
  const [kbMsg, setKbMsg] = useState(null); // { type: 'success'|'error', text: string }
  const [kbActiveTab, setKbActiveTab] = useState('browse'); // 'browse' | 'add-faq' | 'upload-file'
  // Add FAQ form
  const [kbFaqTitle, setKbFaqTitle] = useState('');
  const [kbFaqContent, setKbFaqContent] = useState('');
  const [kbFaqCategory, setKbFaqCategory] = useState('General');
  const [kbFaqTags, setKbFaqTags] = useState('');
  // Upload file form
  const [kbFileCategory, setKbFileCategory] = useState('Uploaded Document');
  const [kbFileTags, setKbFileTags] = useState('');
  const kbFileInputRef = useRef(null);
  const [kbSelectedFile, setKbSelectedFile] = useState(null);
  const [kbSearchQuery, setKbSearchQuery] = useState('');

  const socketRef = useRef(null);
  const chatEndRef = useRef(null);

  // Load replays from backend on mount
  useEffect(() => {
    fetch('http://localhost:8000/api/replays')
      .then(res => res.json())
      .then(data => {
        setReplays(data);
        if (data.length > 0) setReplayId(data[0].id);
      })
      .catch(err => console.error("Error loading replay list", err));
  }, []);

  // Scroll to bottom of chat on message updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Handle Replay Scenario Sync
  const handleReplayChange = (e) => {
    const repId = e.target.value;
    setReplayId(repId);
    const selected = replays.find(r => r.id === repId);
    if (selected) {
      setScenario(selected.scenario);
      setPersonality(selected.personality);
    }
  };

  // Start Coaching Session
  const startSession = async () => {
    try {
      // 1. Reset state
      setMessages([]);
      setReportData(null);
      setShowReport(false);
      setHasMoreReplay(true);
      setIsTyping(false);
      setInputText("");
      setCustomerInputText("");
      
      // 2. Request backend setup
      const res = await fetch('http://localhost:8000/api/sessions/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, scenario, personality })
      });
      const data = await res.json();
      
      setSessionId(data.session_id);
      
      // 3. Connect WebSocket
      const wsUrl = `ws://localhost:8000/ws/coaching/${data.session_id}`;
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        console.log("WebSocket coaching connection established.");
        // Trigger simulation start
        socket.send(JSON.stringify({ action: "start" }));
        if (mode === "Simulator") {
          setIsTyping(true);
        }
      };

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        
        if (payload.type === "turn") {
          setMessages(prev => [...prev, payload.message]);
          setActiveAnalysis(payload.analysis);
          setIsTyping(false);
        } 
        else if (payload.type === "agent_grade") {
          // Update the message log (grades attached)
          setMessages(prev => [...prev, payload.message]);
          setActiveAnalysis(payload.analysis);
          // If in simulator, wait for client turn
          if (mode === "Simulator") {
            setIsTyping(true);
          }
        }
        else if (payload.type === "replay_turn") {
          setMessages(prev => [...prev, payload.message]);
          setActiveAnalysis(payload.analysis);
          setHasMoreReplay(payload.has_more);
        }
      };

      socket.onclose = () => {
        console.log("WebSocket coaching connection closed.");
        setIsTyping(false);
      };

      socket.onerror = (err) => {
        console.error("WebSocket error", err);
        setIsTyping(false);
      };

    } catch (err) {
      console.error("Failed to start session:", err);
    }
  };

  // Agent Sends Message
  const sendAgentMessage = (textToSend = null) => {
    const text = textToSend !== null ? textToSend : inputText;
    if (!text.trim() || !socketRef.current) return;

    // Send via socket
    socketRef.current.send(JSON.stringify({
      action: "agent_message",
      text: text
    }));

    if (textToSend === null) {
      setInputText("");
    }
  };

  // Manual Customer Input (Manual Mode only)
  const sendManualCustomerMessage = () => {
    if (!customerInputText.trim() || !socketRef.current) return;
    
    socketRef.current.send(JSON.stringify({
      action: "customer_message",
      text: customerInputText
    }));
    
    setCustomerInputText("");
  };

  // Advance Replay (Replay Mode only)
  const advanceReplay = () => {
    if (!socketRef.current || !hasMoreReplay) return;
    
    socketRef.current.send(JSON.stringify({
      action: "replay_next"
    }));
  };

  // End Session & Generate Report
  const endSession = async () => {
    if (!sessionId) return;
    
    try {
      // Close WebSocket safely
      if (socketRef.current) {
        socketRef.current.close();
      }
      
      const res = await fetch(`http://localhost:8000/api/sessions/${sessionId}/report`, {
        method: 'POST'
      });
      const report = await res.json();
      
      setReportData(report);
      setShowReport(true);
    } catch (err) {
      console.error("Error generating report", err);
    }
  };

  // Open Performance Analytics Dashboard
  const openAnalytics = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/analytics');
      const data = await res.json();
      setAnalyticsData(data);
      setShowAnalytics(true);
    } catch (err) {
      console.error("Error generating analytics report", err);
    }
  };

  // Open Knowledge Base Manager
  const openKB = async () => {
    setShowKB(true);
    setKbActiveTab('browse');
    setKbMsg(null);
    await refreshKBDocuments();
  };

  const refreshKBDocuments = async () => {
    setKbLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/knowledge');
      const data = await res.json();
      setKbDocuments(data.documents || []);
    } catch (err) {
      console.error('Error loading KB documents', err);
      setKbMsg({ type: 'error', text: 'Failed to load knowledge base documents.' });
    } finally {
      setKbLoading(false);
    }
  };

  const handleKBAddFaq = async () => {
    if (!kbFaqTitle.trim() || !kbFaqContent.trim()) {
      setKbMsg({ type: 'error', text: 'Title and content are required.' });
      return;
    }
    setKbUploadLoading(true);
    setKbMsg(null);
    try {
      const res = await fetch('http://localhost:8000/api/knowledge/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: kbFaqTitle,
          content: kbFaqContent,
          category: kbFaqCategory || 'General',
          tags: kbFaqTags.split(',').map(t => t.trim()).filter(Boolean),
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to add document.');
      }
      setKbMsg({ type: 'success', text: `✓ Article "${kbFaqTitle}" added to knowledge base successfully.` });
      setKbFaqTitle(''); setKbFaqContent(''); setKbFaqCategory('General'); setKbFaqTags('');
      await refreshKBDocuments();
      setKbActiveTab('browse');
    } catch (err) {
      setKbMsg({ type: 'error', text: err.message || 'Error adding article.' });
    } finally {
      setKbUploadLoading(false);
    }
  };

  const handleKBUploadFile = async () => {
    if (!kbSelectedFile) {
      setKbMsg({ type: 'error', text: 'Please select a file to upload.' });
      return;
    }
    setKbUploadLoading(true);
    setKbMsg(null);
    const formData = new FormData();
    formData.append('file', kbSelectedFile);
    formData.append('category', kbFileCategory || 'Uploaded Document');
    formData.append('tags', kbFileTags);
    try {
      const res = await fetch('http://localhost:8000/api/knowledge/upload-file', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'File upload failed.');
      }
      const data = await res.json();
      setKbMsg({ type: 'success', text: `✓ File "${kbSelectedFile.name}" ingested as "${data.document?.title}" successfully.` });
      setKbSelectedFile(null);
      if (kbFileInputRef.current) kbFileInputRef.current.value = '';
      setKbFileTags('');
      await refreshKBDocuments();
      setKbActiveTab('browse');
    } catch (err) {
      setKbMsg({ type: 'error', text: err.message || 'Error uploading file.' });
    } finally {
      setKbUploadLoading(false);
    }
  };

  const handleKBDelete = async (docId, docTitle) => {
    if (!window.confirm(`Delete "${docTitle}" from the knowledge base?`)) return;
    try {
      const res = await fetch(`http://localhost:8000/api/knowledge/${docId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not delete document.');
      }
      setKbMsg({ type: 'success', text: `✓ "${docTitle}" removed from knowledge base.` });
      await refreshKBDocuments();
    } catch (err) {
      setKbMsg({ type: 'error', text: err.message });
    }
  };

  // Quick Action: Apply suggestion to text box
  const applySuggestion = (text) => {
    setInputText(text);
  };

  // Quick Action: Directly send suggestion
  const sendSuggestion = (text) => {
    sendAgentMessage(text);
  };

  // Color mappings helper for styling indicators
  const getRiskBadge = (risk) => {
    if (risk === "High") return "badge badge-danger";
    if (risk === "Medium") return "badge badge-warning";
    return "badge badge-success";
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case "Angry":
        return (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 16.5c1.2-1 2.8-1 4 0" />
            <line x1="8" y1="9" x2="10" y2="10.5" />
            <line x1="10" y1="9" x2="8" y2="10.5" />
            <line x1="14" y1="9" x2="16" y2="10.5" />
            <line x1="16" y1="9" x2="14" y2="10.5" />
          </svg>
        );
      case "Frustrated":
        return (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 16h8" />
            <line x1="8" y1="9.5" x2="10.5" y2="9.5" />
            <line x1="13.5" y1="9.5" x2="16" y2="9.5" />
          </svg>
        );
      case "Satisfied":
        return (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 14s1.5 2 4 2 4-2 4-2" />
            <circle cx="9" cy="9.5" r="1" fill="currentColor" />
            <circle cx="15" cy="9.5" r="1" fill="currentColor" />
          </svg>
        );
      default:
        return (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="8" y1="15" x2="16" y2="15" />
            <circle cx="9" cy="9.5" r="1" fill="currentColor" />
            <circle cx="15" cy="9.5" r="1" fill="currentColor" />
          </svg>
        );
    }
  };

  const getSentimentGlow = (sentiment) => {
    switch (sentiment) {
      case "Angry": return "rgba(239, 68, 68, 0.4)";
      case "Frustrated": return "rgba(245, 158, 11, 0.4)";
      case "Satisfied": return "rgba(16, 185, 129, 0.4)";
      default: return "rgba(0, 240, 255, 0.2)";
    }
  };

  // Custom SVG Sentiment Graph calculations
  const renderSentimentJourney = () => {
    if (!reportData || !reportData.sentiment_journey || reportData.sentiment_journey.length === 0) {
      return <div className="text-muted text-center pt-8">No journey recorded.</div>;
    }

    const journey = reportData.sentiment_journey;
    const sentimentMap = {
      'Angry': 120,
      'Frustrated': 90,
      'Neutral': 60,
      'Satisfied': 30
    };

    const width = 500;
    const height = 150;
    const paddingX = 40;
    const stepX = journey.length > 1 ? (width - paddingX * 2) / (journey.length - 1) : 0;

    const points = journey.map((s, idx) => {
      const x = paddingX + idx * stepX;
      const y = sentimentMap[s] || 60;
      return { x, y, val: s };
    });

    const pathD = points.length > 0 
      ? `M ${points[0].x},${points[0].y} ` + points.slice(1).map(p => `L ${p.x},${p.y}`).join(' ')
      : '';

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
        {/* Horizontal gridlines */}
        <line x1="0" y1="30" x2={width} y2="30" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />
        <line x1="0" y1="60" x2={width} y2="60" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />
        <line x1="0" y1="90" x2={width} y2="90" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />
        <line x1="0" y1="120" x2={width} y2="120" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />

        {/* Labels */}
        <text x="5" y="34" fill="#94a3b8" fontSize="10">Satisfied</text>
        <text x="5" y="64" fill="#94a3b8" fontSize="10">Neutral</text>
        <text x="5" y="94" fill="#94a3b8" fontSize="10">Frustrated</text>
        <text x="5" y="124" fill="#94a3b8" fontSize="10">Angry</text>

        {/* Line Path */}
        {points.length > 1 && (
          <path d={pathD} fill="none" stroke="url(#lineGradient)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        )}

        {/* Data points */}
        {points.map((p, idx) => (
          <g key={idx}>
            <circle cx={p.x} cy={p.y} r="5" fill="#00f0ff" stroke="#080711" strokeWidth="2" />
            <title>{`Turn ${idx + 1}: ${p.val}`}</title>
          </g>
        ))}

        {/* Definitions for Gradients */}
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#d946ef" />
            <stop offset="100%" stopColor="#00f0ff" />
          </linearGradient>
        </defs>
      </svg>
    );
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
          <span>AI CUSTOMER SUPPORT <span style={{ fontSize: '0.8rem', fontWeight: 400, opacity: 0.7 }}>// Coaching Assistant</span></span>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {sessionId && (
            <span className="badge badge-info" style={{ animation: 'fadeIn 0.5s ease' }}>
              Active Session: {sessionId.substring(0, 8)}...
            </span>
          )}
          <button className="btn btn-primary" onClick={openKB} style={{ padding: '6px 12px', fontSize: '0.8rem', background: 'linear-gradient(135deg, #7c3aed, #d946ef)' }}>
            📚 KNOWLEDGE BASE
          </button>
          <button className="btn btn-primary" onClick={openAnalytics} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
            ANALYTICS TRENDS
          </button>
          <button className="btn btn-secondary" onClick={() => window.open('https://github.com', '_blank')} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
            DOCS
          </button>
        </div>
      </header>

      {/* Main Panel Layout */}
      <main className="dashboard-main">
        {/* Left Hand Setup Column */}
        <aside className="glass-panel config-sidebar">
          <div style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '12px', marginBottom: '8px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem' }}>Configuration Panel</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>Establish session properties before simulation.</p>
          </div>

          <div className="form-group">
            <label className="form-label">Interaction Mode</label>
            <select className="form-select" value={mode} onChange={(e) => setMode(e.target.value)} disabled={sessionId !== null}>
              <option value="Simulator">Simulator Mode (Automated AI Customer)</option>
              <option value="Manual">Manual Mode (Paste customer messages)</option>
              <option value="Replay">Replay Mode (Step pre-loaded chats)</option>
            </select>
          </div>

          {mode === "Replay" ? (
            <div className="form-group">
              <label className="form-label">Preloaded Transcripts</label>
              <select className="form-select" value={replayId} onChange={handleReplayChange} disabled={sessionId !== null}>
                {replays.map(r => (
                  <option key={r.id} value={r.id}>{r.title} ({r.scenario})</option>
                ))}
              </select>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Simulation Scenario</label>
                <select className="form-select" value={scenario} onChange={(e) => setScenario(e.target.value)} disabled={sessionId !== null}>
                  {SCENARIOS.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Customer Personality</label>
                <select className="form-select" value={personality} onChange={(e) => setPersonality(e.target.value)} disabled={sessionId !== null}>
                  {PERSONALITIES.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {!sessionId ? (
              <button className="btn btn-primary" onClick={startSession}>
                START SUPPORT SESSION
              </button>
            ) : (
              <>
                <button className="btn btn-danger" onClick={endSession}>
                  END CONVERSATION & REPORT
                </button>
                <button className="btn btn-secondary" onClick={() => setSessionId(null)}>
                  RESET CONSOLE
                </button>
              </>
            )}
          </div>

          <div className="glass-card" style={{ marginTop: 'auto', background: 'rgba(255, 255, 255, 0.01)' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-primary)', textTransform: 'uppercase', marginBottom: '6px' }}>Console Status</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: sessionId ? 'var(--color-success)' : 'var(--color-warning)', boxShadow: sessionId ? '0 0 10px var(--color-success)' : 'none' }}></span>
              <span>{sessionId ? 'Running active analysis pipeline' : 'System idle, awaiting selection'}</span>
            </div>
          </div>
        </aside>

        {/* Right Active Workspaces: Three Panel Console */}
        <section className="console-container">
          {/* Panel 1: Customer Chat Workspace */}
          <article className="glass-panel console-panel">
            <div className="panel-header">
              <span className="panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Chat Panel
              </span>
              <span className="badge badge-info">{mode}</span>
            </div>
            
            <div className="chat-container">
              {/* Chat bubbles */}
              <div className="chat-messages">
                {activeAnalysis.escalation_risk === "High" && (
                  <div className="escalation-warning-overlay">
                    <div>
                      <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--color-danger)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                        ⚠️ CRITICAL ESCALATION RISK DETECTED
                      </span>
                      <p style={{ fontSize: '0.82rem', lineHeight: 1.4, color: 'var(--text-main)' }}>
                        <strong>Reasoning:</strong> {activeAnalysis.escalation_reasoning}
                      </p>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>
                        <strong>Intervention Strategy:</strong> {activeAnalysis.intervention_strategy}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexDirection: 'column', minWidth: '150px' }}>
                      <button className="btn btn-primary" style={{ padding: '6px 10px', fontSize: '0.72rem', background: 'var(--color-danger)', color: '#fff', boxShadow: 'none' }} onClick={() => sendAgentMessage(activeAnalysis.intervention_strategy)}>
                        Send recommended action
                      </button>
                      <button className="btn btn-secondary" style={{ padding: '6px 10px', fontSize: '0.72rem' }} onClick={endSession}>
                        End & escalate to supervisor
                      </button>
                    </div>
                  </div>
                )}
                {messages.length === 0 && (
                  <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-dark)', padding: '20px' }}>
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ marginBottom: '12px', opacity: 0.5 }}>
                      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                    </svg>
                    <p style={{ fontSize: '0.9rem' }}>No active chat history. Click 'Start Support Session' to begin coaching.</p>
                  </div>
                )}
                
                {messages.map((m, idx) => (
                  <div key={m.id || idx} className={m.sender === 'customer' ? 'chat-bubble chat-bubble-customer' : 'chat-bubble chat-bubble-agent'}>
                    <span className="chat-sender-label">
                      {m.sender === 'customer' ? `CUSTOMER (${personality})` : 'AGENT (YOU)'}
                    </span>
                    <div>{m.text}</div>
                  </div>
                ))}

                {isTyping && (
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Chat Input / Composer based on Mode */}
              <div className="chat-composer">
                {mode === "Simulator" && (
                  <>
                    <input 
                      type="text" 
                      className="form-input chat-composer-input glow-border-primary" 
                      placeholder={sessionId ? "Formulate response..." : "Start session first..."}
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      disabled={!sessionId}
                      onKeyDown={(e) => e.key === 'Enter' && sendAgentMessage()}
                    />
                    <button className="btn btn-primary" onClick={() => sendAgentMessage()} disabled={!sessionId}>
                      SEND
                    </button>
                  </>
                )}

                {mode === "Manual" && (
                  <div style={{ display: 'flex', flexDirection: 'column', width: '100%', gap: '10px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input 
                        type="text" 
                        className="form-input" 
                        style={{ flex: 1, borderLeft: '3px solid var(--color-primary)' }}
                        placeholder="Paste incoming Customer message..."
                        value={customerInputText}
                        onChange={(e) => setCustomerInputText(e.target.value)}
                        disabled={!sessionId}
                        onKeyDown={(e) => e.key === 'Enter' && sendManualCustomerMessage()}
                      />
                      <button className="btn btn-secondary" onClick={sendManualCustomerMessage} disabled={!sessionId}>
                        ADD CLIENT TURN
                      </button>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input 
                        type="text" 
                        className="form-input" 
                        style={{ flex: 1, borderLeft: '3px solid var(--color-secondary)' }}
                        placeholder="Type/send Agent reply..."
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        disabled={!sessionId}
                        onKeyDown={(e) => e.key === 'Enter' && sendAgentMessage()}
                      />
                      <button className="btn btn-primary" onClick={() => sendAgentMessage()} disabled={!sessionId}>
                        SEND AGENT TURN
                      </button>
                    </div>
                  </div>
                )}

                {mode === "Replay" && (
                  <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
                    <button 
                      className="btn btn-primary" 
                      onClick={advanceReplay} 
                      disabled={!sessionId || !hasMoreReplay}
                      style={{ width: '100%' }}
                    >
                      {hasMoreReplay ? "ADVANCE TRANSCRIPT (NEXT TURN)" : "TRANSCRIPT ENDED"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </article>

          {/* Panel 2: AI Copilot (Intent, Sentiment, RAG and Escalation) */}
          <article className="glass-panel console-panel">
            <div className="panel-header">
              <span className="panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                AI Copilot Panel
              </span>
              {activeAnalysis.ai_generated === true ? (
                <span
                  className="badge badge-success"
                  title="Every field on this panel came from a live Groq LLM call for this turn."
                >
                  AI-generated
                </span>
              ) : activeAnalysis.ai_generated === false ? (
                <span
                  className="badge badge-warning"
                  title="GROQ_API_KEY isn't active (missing, invalid, or the call failed) — showing built-in standard responses instead."
                >
                  Standard mode
                </span>
              ) : (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Real-time</span>
              )}
            </div>

            <div className="panel-body">
              {/* Intent & Sentiment Tracker */}
              <div className="glass-card" style={{ display: 'flex', gap: '16px', alignItems: 'center', background: 'rgba(255,255,255,0.015)' }}>
                <div 
                  style={{ 
                    width: '60px', 
                    height: '60px', 
                    borderRadius: '50%', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    color: 'var(--text-h)',
                    background: getSentimentGlow(activeAnalysis.sentiment),
                    boxShadow: `0 0 20px ${getSentimentGlow(activeAnalysis.sentiment)}`,
                    transition: 'var(--transition-smooth)'
                  }}
                >
                  {getSentimentIcon(activeAnalysis.sentiment)}
                </div>
                <div>
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: 'var(--text-muted)' }}>Customer Status</h4>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
                    <span className="badge badge-info">{activeAnalysis.intent}</span>
                    <span className="badge badge-danger">{activeAnalysis.sentiment}</span>
                  </div>
                </div>
              </div>

              {/* Escalation Risk Monitor */}
              {activeAnalysis.escalation_risk === 'Low' ? (
                <div
                  className="glass-card"
                  style={{
                    borderLeft: '4px solid var(--color-success)',
                    background: 'rgba(255,255,255,0.01)',
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px'
                  }}
                >
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                    No escalation risk detected — proceeding normally.
                  </span>
                  <span className={getRiskBadge(activeAnalysis.escalation_risk)}>LOW RISK</span>
                </div>
              ) : (
                <div className="glass-card" style={{ borderLeft: activeAnalysis.escalation_risk === 'High' ? '4px solid var(--color-danger)' : '4px solid var(--color-warning)', background: 'rgba(255,255,255,0.01)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 700 }}>Escalation Risk Analysis</h4>
                    <span className={getRiskBadge(activeAnalysis.escalation_risk)}>{activeAnalysis.escalation_risk} RISK</span>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-main)', lineHeight: 1.4, marginBottom: '10px' }}>
                    <strong>Reasoning:</strong> {activeAnalysis.escalation_reasoning}
                  </p>
                  <div style={{ padding: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '0.8rem', borderLeft: '2px solid var(--color-info)' }}>
                    <strong>Recommended action:</strong> {activeAnalysis.intervention_strategy}
                  </div>
                </div>
              )}

              {/* RAG Knowledge Recommendations */}
              <div>
                <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                  </svg>
                  Related knowledge base articles
                </h4>
                {activeAnalysis.retrieved_documents.length === 0 ? (
                  <div className="glass-card text-center" style={{ color: 'var(--text-dark)', fontSize: '0.8rem' }}>
                    Awaiting message input to pull articles...
                  </div>
                ) : (
                  activeAnalysis.retrieved_documents.map((doc, idx) => {
                    const docKey = doc.id || idx;
                    const isExpanded = !!expandedRagDocs[docKey];
                    const isLong = doc.content.length > 140;
                    const displayText = isExpanded || !isLong ? doc.content : doc.content.slice(0, 140).trim() + '…';
                    return (
                      <div key={docKey} className="glass-card rag-card">
                        <div className="rag-card-header">
                          <span>{doc.title}</span>
                          <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>({doc.category})</span>
                        </div>
                        <div className="rag-card-body">
                          {displayText}
                          {isLong && (
                            <button
                              onClick={() => setExpandedRagDocs(prev => ({ ...prev, [docKey]: !prev[docKey] }))}
                              style={{
                                display: 'block',
                                marginTop: '6px',
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                color: 'var(--color-primary)',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                cursor: 'pointer'
                              }}
                            >
                              {isExpanded ? 'Show less' : 'Show more'}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </article>

          {/* Panel 3: Reply Suggestions & Coaching Tips */}
          <article className="glass-panel console-panel">
            <div className="panel-header">
              <span className="panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
                Suggestions & Coaching
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Coaching</span>
            </div>

            <div className="panel-body">
              {/* Agent Performance Grade/Critique (if last response evaluated) */}
              {activeAnalysis.agent_evaluation && (
                <div className="glass-card" style={{ background: 'rgba(217, 70, 239, 0.03)', border: '1px solid rgba(217, 70, 239, 0.15)' }}>
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-secondary)', marginBottom: '10px' }}>
                    Agent Turn Evaluation
                  </h4>
                  <div style={{ display: 'flex', gap: '20px', marginBottom: '10px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '3px' }}>
                        <span>Empathy</span>
                        <span>{activeAnalysis.agent_evaluation.empathy_score}%</span>
                      </div>
                      <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{ width: `${activeAnalysis.agent_evaluation.empathy_score}%`, height: '100%', background: 'var(--color-secondary)' }}></div>
                      </div>
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '3px' }}>
                        <span>Clarity</span>
                        <span>{activeAnalysis.agent_evaluation.clarity_score}%</span>
                      </div>
                      <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{ width: `${activeAnalysis.agent_evaluation.clarity_score}%`, height: '100%', background: 'var(--color-primary)' }}></div>
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-main)', lineHeight: 1.45 }}>
                    <strong>Coach Critique:</strong> {activeAnalysis.agent_evaluation.critique}
                  </p>
                </div>
              )}

              {/* Dynamic Suggestions */}
              <div>
                <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 700, marginBottom: '10px' }}>
                  Real-Time suggested Replies
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {activeAnalysis.suggestions.length === 0 ? (
                    <div className="glass-card text-center" style={{ color: 'var(--text-dark)', fontSize: '0.8rem' }}>
                      Awaiting message to structure suggestions...
                    </div>
                  ) : (
                    activeAnalysis.suggestions.map((sug, idx) => (
                      <div key={idx} className="suggestion-card">
                        <div className="suggestion-card-type">{sug.type}</div>
                        <div className="suggestion-card-text">"{sug.text}"</div>
                        <div className="suggestion-card-rationale">{sug.rationale}</div>
                        <div className="suggestion-actions">
                          <button
                            className="btn btn-secondary"
                            style={{ flex: 1, padding: '6px 12px', fontSize: '0.8rem' }}
                            title="Puts this text in the reply box so you can edit it before sending"
                            onClick={() => applySuggestion(sug.text)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                            </svg>
                            Edit &amp; send
                          </button>
                          <button
                            className="btn btn-primary"
                            style={{ flex: 1, padding: '6px 12px', fontSize: '0.8rem' }}
                            title="Sends this reply to the customer immediately, as-is"
                            onClick={() => sendSuggestion(sug.text)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="m22 2-7 20-4-9-9-4Z" />
                              <path d="M22 2 11 13" />
                            </svg>
                            Send as-is
                          </button>

                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Coaching tips checklist */}
              <div>
                <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 700, marginBottom: '10px' }}>
                  Dynamic Coaching Tips
                </h4>
                <ul style={{ listStyleType: 'none', fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {activeAnalysis.coaching_tips.map((tip, idx) => (
                    <li key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', color: 'var(--text-main)', lineHeight: 1.4 }}>
                      <span style={{ color: 'var(--color-primary)', fontWeight: 'bold' }}>•</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        </section>
      </main>

      {/* Performance Report Overlay Modal */}
      {showReport && reportData && (
        <div className="report-overlay">
          <div className="report-modal">
            <div className="report-header">
              <div className="report-title-section">
                <span className="report-title">{reportData.title}</span>
                <span className="report-subtitle">Coaching Session Performance Assessment Report</span>
              </div>
              <button className="btn btn-secondary" onClick={() => setShowReport(false)} style={{ padding: '6px 12px' }}>
                CLOSE
              </button>
            </div>

            <div className="report-grid">
              {/* Left Column: Quality Circular Gauge & bar graphs */}
              <div className="gauge-container">
                <div className="gauge">
                  <svg className="gauge-svg" viewBox="0 0 100 100">
                    <circle className="gauge-track" cx="50" cy="50" r="42" />
                    <circle 
                      className="gauge-fill" 
                      cx="50" 
                      cy="50" 
                      r="42" 
                      strokeDasharray={`${2 * Math.PI * 42}`}
                      strokeDashoffset={`${2 * Math.PI * 42 * (1 - reportData.resolution_quality_score / 100)}`}
                    />
                    <defs>
                      <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#00f0ff" />
                        <stop offset="100%" stopColor="#d946ef" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="gauge-value">
                    <span>{reportData.resolution_quality_score}</span>
                    <span className="gauge-label">SCORE</span>
                  </div>
                </div>

                <div style={{ width: '100%', marginTop: '16px' }} className="competency-list">
                  <div className="competency-item">
                    <div className="competency-meta">
                      <span>Empathy</span>
                      <span>{reportData.competencies.empathy}%</span>
                    </div>
                    <div className="competency-bar-track">
                      <div className="competency-bar-fill" style={{ width: `${reportData.competencies.empathy}%`, background: 'var(--color-secondary)' }}></div>
                    </div>
                  </div>
                  <div className="competency-item">
                    <div className="competency-meta">
                      <span>Clarity</span>
                      <span>{reportData.competencies.clarity}%</span>
                    </div>
                    <div className="competency-bar-track">
                      <div className="competency-bar-fill" style={{ width: `${reportData.competencies.clarity}%`, background: 'var(--color-primary)' }}></div>
                    </div>
                  </div>
                  <div className="competency-item">
                    <div className="competency-meta">
                      <span>Policy Compliance</span>
                      <span>{reportData.competencies.policy_compliance}%</span>
                    </div>
                    <div className="competency-bar-track">
                      <div className="competency-bar-fill" style={{ width: `${reportData.competencies.policy_compliance}%`, background: 'var(--color-success)' }}></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Sentiment journey and textual feedback */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="sentiment-journey-container">
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700 }}>Customer Sentiment Journey</h4>
                  <div className="sentiment-chart-box">
                    {renderSentimentJourney()}
                  </div>
                </div>

                <div className="glass-card">
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.95rem', fontWeight: 700, marginBottom: '8px' }}>Conversation Outcome</h4>
                  <p style={{ fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--text-main)' }}>
                    {reportData.conversation_summary}
                  </p>
                </div>

                <div className="glass-card" style={{ borderLeft: '3px solid var(--color-primary)', background: 'rgba(0, 240, 255, 0.01)' }}>
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.95rem', fontWeight: 700, marginBottom: '8px', color: 'var(--color-primary)' }}>
                    Personalized Coaching Recommendations
                  </h4>
                  <ul style={{ listStyleType: 'none', fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {reportData.recommendations.map((rec, idx) => (
                      <li key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', lineHeight: 1.4 }}>
                        <span style={{ color: 'var(--color-primary)', fontWeight: 'bold' }}>✓</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showAnalytics && analyticsData && (
        <div className="analytics-overlay">
          <div className="analytics-modal">
            <div className="report-header">
              <div className="report-title-section">
                <span className="report-title">Coaching Analytics Dashboard</span>
                <span className="report-subtitle">Aggregated coaching metrics and agent improvement indicators across multiple support sessions</span>
              </div>
              <button className="btn btn-secondary" onClick={() => setShowAnalytics(false)} style={{ padding: '6px 12px' }}>
                CLOSE
              </button>
            </div>

            {/* KPI Metrics */}
            <div className="analytics-kpi-grid">
              <div className="analytics-kpi-card">
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Total Sessions Logged</span>
                <span className="analytics-kpi-value">{analyticsData.total_sessions}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-success)' }}>✓ Complete history track</span>
              </div>
              <div className="analytics-kpi-card">
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Average Resolution Score</span>
                <span className="analytics-kpi-value">{analyticsData.avg_quality_score}%</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Target: &gt;85% average</span>
              </div>
              <div className="analytics-kpi-card">
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Customer Escalation Rate</span>
                <span className="analytics-kpi-value" style={{ color: analyticsData.escalation_rate > 30 ? 'var(--color-warning)' : 'var(--color-success)', textShadow: 'none' }}>
                  {analyticsData.escalation_rate}%
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SLA threshold: &lt;15%</span>
              </div>
            </div>

            <div className="analytics-dashboard-grid">
              {/* Left Column: Historical Session Logs Table & Quality Score Trend Chart */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="glass-card">
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700, marginBottom: '12px' }}>
                    Agent Quality Improvement Trend
                  </h4>
                  <div style={{ height: '150px', background: 'rgba(8,7,17,0.4)', borderRadius: '8px', padding: '16px' }}>
                    {/* SVG Quality Score Trend Chart */}
                    <svg viewBox="0 0 450 120" className="w-full h-full">
                      {/* Gridlines */}
                      <line x1="0" y1="20" x2="450" y2="20" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />
                      <line x1="0" y1="60" x2="450" y2="60" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />
                      <line x1="0" y1="100" x2="450" y2="100" stroke="rgba(255,255,255,0.05)" strokeDasharray="4" />

                      <text x="5" y="15" fill="#94a3b8" fontSize="8">100%</text>
                      <text x="5" y="55" fill="#94a3b8" fontSize="8">50%</text>
                      <text x="5" y="95" fill="#94a3b8" fontSize="8">0%</text>

                      {/* Line */}
                      {analyticsData.improvement_trend.length > 0 && (() => {
                        const width = 450;
                        const paddingX = 40;
                        const stepX = analyticsData.improvement_trend.length > 1 ? (width - paddingX * 2) / (analyticsData.improvement_trend.length - 1) : 0;
                        const points = analyticsData.improvement_trend.map((score, idx) => {
                          const x = paddingX + idx * stepX;
                          const y = 120 - (score * 100 / 100); // map 0-100 to y=100 to y=20
                          return { x, y, val: score };
                        });
                        const pathD = `M ${points[0].x},${points[0].y} ` + points.slice(1).map(p => `L ${p.x},${p.y}`).join(' ');
                        return (
                          <>
                            {points.length > 1 && (
                              <path d={pathD} fill="none" stroke="var(--color-primary)" strokeWidth="2.5" strokeLinecap="round" />
                            )}
                            {points.map((p, idx) => (
                              <g key={idx}>
                                <circle cx={p.x} cy={p.y} r="4" fill="#00f0ff" stroke="#080711" strokeWidth="2" />
                                <text x={p.x - 6} y={p.y - 8} fill="#fff" fontSize="8" fontWeight="600">{p.val}%</text>
                              </g>
                            ))}
                          </>
                        );
                      })()}
                    </svg>
                  </div>
                </div>

                <div className="glass-card">
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700, marginBottom: '12px' }}>
                    Historical Coaching Sessions
                  </h4>
                  <div className="history-table-container">
                    <table className="history-table">
                      <thead>
                        <tr>
                          <th>Session ID</th>
                          <th>Scenario / Description</th>
                          <th>Interaction Mode</th>
                          <th>Quality Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsData.historical_sessions.map((sess, idx) => (
                          <tr key={sess.session_id || idx}>
                            <td style={{ fontFamily: 'monospace', color: 'var(--color-primary)' }}>
                              {sess.session_id.substring(0, 8)}...
                            </td>
                            <td>{sess.title || sess.scenario}</td>
                            <td>
                              <span className="badge badge-info">{sess.mode}</span>
                            </td>
                            <td style={{ fontWeight: 'bold', color: sess.resolution_quality_score >= 85 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                              {sess.resolution_quality_score}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Right Column: Common Escalation Triggers and Knowledge Gaps */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="glass-card" style={{ borderLeft: '3px solid var(--color-danger)' }}>
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700, marginBottom: '12px' }}>
                    Common Escalation Triggers
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {Object.entries(analyticsData.common_triggers).map(([scenario, count]) => (
                      <div key={scenario} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.02)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{scenario}</span>
                        <span className="badge badge-danger">{count} Triggered</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="glass-card" style={{ borderLeft: '3px solid var(--color-warning)' }}>
                  <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700, marginBottom: '12px' }}>
                    Detected Knowledge Gaps (RAG Analysis)
                  </h4>
                  <div className="gap-list">
                    {analyticsData.knowledge_gaps.map((gap, idx) => (
                      <div key={idx} className="gap-item">
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '0.85rem', marginBottom: '4px' }}>
                          <span>Topic: {gap.topic}</span>
                          <span style={{ color: 'var(--color-warning)' }}>Score: {gap.avg_score}%</span>
                        </div>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                          <strong>Recommended Remedy:</strong> {gap.remedy}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========== Knowledge Base Manager Modal ========== */}
      {showKB && (
        <div className="analytics-overlay" style={{ zIndex: 2000 }}>
          <div className="analytics-modal" style={{ maxWidth: '900px', width: '95vw', maxHeight: '90vh', overflowY: 'auto' }}>

            {/* Header */}
            <div className="report-header" style={{ background: 'linear-gradient(135deg, rgba(124,58,237,0.15), rgba(217,70,239,0.1))', borderBottom: '1px solid rgba(124,58,237,0.3)' }}>
              <div className="report-title-section">
                <span className="report-title" style={{ background: 'linear-gradient(135deg, #a78bfa, #f0abfc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>📚 Knowledge Base Manager</span>
                <span className="report-subtitle">Add FAQs, upload PDFs & documents, or manage existing articles. Changes are applied instantly to the RAG pipeline.</span>
              </div>
              <button className="btn btn-secondary" onClick={() => setShowKB(false)} style={{ padding: '6px 12px' }}>CLOSE</button>
            </div>

            {/* Status message */}
            {kbMsg && (
              <div style={{
                margin: '16px 0 0',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 500,
                background: kbMsg.type === 'success' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
                border: `1px solid ${kbMsg.type === 'success' ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
                color: kbMsg.type === 'success' ? 'var(--color-success)' : 'var(--color-danger)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
              }}>
                <span>{kbMsg.text}</span>
                <button onClick={() => setKbMsg(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: '1rem' }}>×</button>
              </div>
            )}

            {/* Tab Navigation */}
            <div style={{ display: 'flex', gap: '4px', marginTop: '20px', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0' }}>
              {[{ id: 'browse', label: '🗂 Browse Articles', count: kbDocuments.length },
                { id: 'add-faq', label: '✏️ Add FAQ / Article' },
                { id: 'upload-file', label: '📤 Upload File (PDF, DOCX, TXT)' }].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => { setKbActiveTab(tab.id); setKbMsg(null); }}
                  style={{
                    padding: '10px 18px',
                    border: 'none',
                    borderBottom: kbActiveTab === tab.id ? '2px solid #a78bfa' : '2px solid transparent',
                    background: kbActiveTab === tab.id ? 'rgba(124,58,237,0.12)' : 'transparent',
                    color: kbActiveTab === tab.id ? '#a78bfa' : 'var(--text-muted)',
                    fontFamily: 'var(--font-display)',
                    fontWeight: kbActiveTab === tab.id ? 700 : 400,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    borderRadius: '6px 6px 0 0',
                    transition: 'all 0.2s ease',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {tab.label}{tab.count !== undefined ? ` (${tab.count})` : ''}
                </button>
              ))}
            </div>

            {/* ---- Tab: Browse Articles ---- */}
            {kbActiveTab === 'browse' && (
              <div style={{ padding: '20px 0' }}>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="🔍 Filter articles by title, category, or tags..."
                    value={kbSearchQuery}
                    onChange={e => setKbSearchQuery(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-secondary" onClick={refreshKBDocuments} disabled={kbLoading} style={{ padding: '8px 16px', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                    {kbLoading ? '...' : '↻ Refresh'}
                  </button>
                </div>

                {kbLoading ? (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Loading knowledge base...</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {kbDocuments
                      .filter(doc => {
                        if (!kbSearchQuery.trim()) return true;
                        const q = kbSearchQuery.toLowerCase();
                        return (
                          doc.title.toLowerCase().includes(q) ||
                          doc.category.toLowerCase().includes(q) ||
                          (doc.tags || []).some(t => t.toLowerCase().includes(q)) ||
                          doc.content.toLowerCase().includes(q)
                        );
                      })
                      .map((doc) => (
                        <div key={doc.id} className="glass-card" style={{
                          display: 'flex', gap: '16px', alignItems: 'flex-start',
                          borderLeft: doc.editable === false ? '3px solid rgba(0,240,255,0.4)' : '3px solid rgba(124,58,237,0.6)',
                          background: 'rgba(255,255,255,0.015)',
                          position: 'relative'
                        }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '6px' }}>
                              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.92rem' }}>{doc.title}</span>
                              <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>{doc.category}</span>
                              {doc.editable === false && <span className="badge" style={{ fontSize: '0.65rem', background: 'rgba(0,240,255,0.1)', color: 'var(--color-primary)', border: '1px solid rgba(0,240,255,0.2)' }}>BUILT-IN</span>}
                              {doc.source && doc.source.startsWith('file:') && <span className="badge" style={{ fontSize: '0.65rem', background: 'rgba(124,58,237,0.15)', color: '#a78bfa', border: '1px solid rgba(124,58,237,0.3)' }}>📎 {doc.source.replace('file:', '')}</span>}
                            </div>
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45, marginBottom: '8px' }}>
                              {doc.content.length > 200 ? doc.content.slice(0, 200) + '...' : doc.content}
                            </p>
                            {doc.tags && doc.tags.length > 0 && (
                              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                                {doc.tags.map((tag, ti) => (
                                  <span key={ti} style={{ fontSize: '0.68rem', padding: '2px 7px', borderRadius: '20px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)', color: 'var(--text-muted)' }}>{tag}</span>
                                ))}
                              </div>
                            )}
                          </div>
                          {doc.editable !== false && (
                            <button
                              onClick={() => handleKBDelete(doc.id, doc.title)}
                              title="Remove from knowledge base"
                              style={{
                                background: 'rgba(239,68,68,0.1)',
                                border: '1px solid rgba(239,68,68,0.25)',
                                borderRadius: '6px',
                                padding: '6px 10px',
                                cursor: 'pointer',
                                color: 'var(--color-danger)',
                                fontSize: '0.8rem',
                                transition: 'all 0.2s ease',
                                flexShrink: 0
                              }}
                            >
                              🗑 Delete
                            </button>
                          )}
                        </div>
                      ))
                    }
                    {kbDocuments.filter(doc => {
                      if (!kbSearchQuery.trim()) return true;
                      const q = kbSearchQuery.toLowerCase();
                      return doc.title.toLowerCase().includes(q) || doc.category.toLowerCase().includes(q) || (doc.tags || []).some(t => t.toLowerCase().includes(q)) || doc.content.toLowerCase().includes(q);
                    }).length === 0 && (
                      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>No articles match your search.</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ---- Tab: Add FAQ / Article ---- */}
            {kbActiveTab === 'add-faq' && (
              <div style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '4px' }}>
                  Add a new FAQ, policy document, or support guide directly as text. This article will immediately be available to the RAG pipeline during coaching sessions.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Article Title *</label>
                    <input className="form-input" type="text" placeholder="e.g. Holiday Return Policy" value={kbFaqTitle} onChange={e => setKbFaqTitle(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Category</label>
                    <input className="form-input" type="text" placeholder="e.g. Billing & Refunds" value={kbFaqCategory} onChange={e => setKbFaqCategory(e.target.value)} list="kb-categories" />
                    <datalist id="kb-categories">
                      <option value="Billing & Refunds" />
                      <option value="Technical Support" />
                      <option value="Account Security" />
                      <option value="Shipping & Delivery" />
                      <option value="General" />
                      <option value="Product Information" />
                    </datalist>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Content / Article Body *</label>
                  <textarea
                    className="form-input"
                    style={{ minHeight: '160px', resize: 'vertical', lineHeight: 1.5, fontFamily: 'inherit' }}
                    placeholder="Write the full policy, FAQ answer, or support procedure here. Be specific — the RAG engine will retrieve this text verbatim when agents need it."
                    value={kbFaqContent}
                    onChange={e => setKbFaqContent(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Tags (comma-separated)</label>
                  <input className="form-input" type="text" placeholder="e.g. holiday, returns, exchange, extended policy" value={kbFaqTags} onChange={e => setKbFaqTags(e.target.value)} />
                  <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>Tags improve search accuracy. Add keywords agents might type when looking for this article.</small>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                  <button
                    className="btn btn-primary"
                    style={{ flex: 1, background: 'linear-gradient(135deg, #7c3aed, #d946ef)', padding: '12px' }}
                    onClick={handleKBAddFaq}
                    disabled={kbUploadLoading || !kbFaqTitle.trim() || !kbFaqContent.trim()}
                  >
                    {kbUploadLoading ? 'Adding...' : '✓ ADD TO KNOWLEDGE BASE'}
                  </button>
                  <button className="btn btn-secondary" onClick={() => { setKbFaqTitle(''); setKbFaqContent(''); setKbFaqCategory('General'); setKbFaqTags(''); }} style={{ padding: '12px 20px' }}>CLEAR</button>
                </div>
              </div>
            )}

            {/* ---- Tab: Upload File ---- */}
            {kbActiveTab === 'upload-file' && (
              <div style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '4px' }}>
                  Upload a PDF, DOCX, TXT, Markdown, or CSV file. The system will automatically extract text content and add it to the knowledge base for RAG-powered retrieval.
                </p>

                {/* Drag-and-drop file area */}
                <div
                  style={{
                    border: '2px dashed rgba(124,58,237,0.5)',
                    borderRadius: '12px',
                    padding: '40px 24px',
                    textAlign: 'center',
                    background: kbSelectedFile ? 'rgba(124,58,237,0.08)' : 'rgba(255,255,255,0.01)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onClick={() => kbFileInputRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); }}
                  onDrop={e => { e.preventDefault(); const file = e.dataTransfer.files[0]; if (file) setKbSelectedFile(file); }}
                >
                  {kbSelectedFile ? (
                    <>
                      <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>📄</div>
                      <div style={{ fontWeight: 700, color: '#a78bfa', marginBottom: '4px' }}>{kbSelectedFile.name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{(kbSelectedFile.size / 1024).toFixed(1)} KB · Click to change file</div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>📂</div>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>Drag & drop a file here or click to browse</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Supported: PDF, DOCX, TXT, MD, CSV · Max 10MB</div>
                    </>
                  )}
                  <input
                    ref={kbFileInputRef}
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.md,.csv,.rst"
                    style={{ display: 'none' }}
                    onChange={e => { if (e.target.files[0]) setKbSelectedFile(e.target.files[0]); }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Document Category</label>
                    <input className="form-input" type="text" placeholder="e.g. Product Manuals" value={kbFileCategory} onChange={e => setKbFileCategory(e.target.value)} list="kb-file-categories" />
                    <datalist id="kb-file-categories">
                      <option value="Uploaded Document" />
                      <option value="Product Manuals" />
                      <option value="Policy Documents" />
                      <option value="Training Material" />
                      <option value="Technical Support" />
                      <option value="Billing & Refunds" />
                    </datalist>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tags (comma-separated)</label>
                    <input className="form-input" type="text" placeholder="e.g. manual, product, setup" value={kbFileTags} onChange={e => setKbFileTags(e.target.value)} />
                  </div>
                </div>

                <button
                  className="btn btn-primary"
                  style={{ background: 'linear-gradient(135deg, #7c3aed, #d946ef)', padding: '14px' }}
                  onClick={handleKBUploadFile}
                  disabled={kbUploadLoading || !kbSelectedFile}
                >
                  {kbUploadLoading ? '⏳ Processing file and ingesting into RAG...' : '📤 UPLOAD & INGEST INTO KNOWLEDGE BASE'}
                </button>

                <div className="glass-card" style={{ borderLeft: '3px solid var(--color-info)', background: 'rgba(0,240,255,0.02)', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  <strong style={{ color: 'var(--color-primary)' }}>How file ingestion works:</strong> Your file's text is extracted, chunked, and added as a new entry in the knowledge base. During coaching sessions, the RAG engine will automatically surface relevant content when customer queries match. For PDF support, ensure the backend has <code style={{ fontFamily: 'monospace', color: '#a78bfa' }}>pypdf</code> installed.
                </div>
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
}

export default App;