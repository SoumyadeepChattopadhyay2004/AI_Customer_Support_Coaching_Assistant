import uuid
from typing import Dict, List, Any

# Simple in-memory database for sessions and reports
conversations: Dict[str, Dict[str, Any]] = {}
reports: Dict[str, Dict[str, Any]] = {}

def create_conversation(mode: str, scenario: str, personality: str) -> str:
    conversation_id = str(uuid.uuid4())
    conversations[conversation_id] = {
        "id": conversation_id,
        "mode": mode,
        "scenario": scenario,
        "personality": personality,
        "messages": [],
        "analysis_history": []
    }
    return conversation_id

def add_message(conversation_id: str, sender: str, text: str) -> Dict[str, Any]:
    if conversation_id not in conversations:
        raise ValueError("Conversation not found")
    
    message = {
        "id": str(uuid.uuid4()),
        "sender": sender, # 'customer', 'agent', or 'system'
        "text": text
    }
    conversations[conversation_id]["messages"].append(message)
    return message

def get_conversation(conversation_id: str) -> Dict[str, Any]:
    return conversations.get(conversation_id)

def save_analysis(conversation_id: str, analysis: Dict[str, Any]):
    if conversation_id in conversations:
        conversations[conversation_id]["analysis_history"].append(analysis)

def save_report(conversation_id: str, report: Dict[str, Any]):
    reports[conversation_id] = report

def get_report(conversation_id: str) -> Dict[str, Any]:
    return reports.get(conversation_id)

def get_all_reports() -> Dict[str, Dict[str, Any]]:
    return reports

def get_all_conversations() -> Dict[str, Dict[str, Any]]:
    return conversations
