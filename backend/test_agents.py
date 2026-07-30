import sys
import os
from dotenv import load_dotenv

# Adjust path to import backend modules correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env (this script doesn't import main.py, so it must load it itself)
load_dotenv()

from backend.agents import agent_orchestrator
from backend.simulator import CustomerSimulator

def test_pipeline():
    print("Testing Customer Simulator...")
    sim = CustomerSimulator("Billing Dispute", "Angry")
    
    # Turn 0
    msg0 = sim.get_next_customer_message()
    print(f"Customer (Angry): {msg0}")
    
    # Run Orchestrator
    history = [{"sender": "customer", "text": msg0}]
    analysis = agent_orchestrator.run_pipeline(history, msg0)
    print(f"Detected Intent: {analysis['intent']}")
    print(f"Detected Sentiment: {analysis['sentiment']}")
    print(f"Escalation Risk: {analysis['escalation_risk']}")
    print(f"Suggestions: {[s['type'] for s in analysis['suggestions']]}")
    print(f"Coaching Tips: {analysis['coaching_tips']}")
    
    # Turn 1 (Agent reply)
    agent_reply = "I understand you were charged twice. Can I please get your email address so I can refund it?"
    print(f"Agent: {agent_reply}")
    history.append({"sender": "agent", "text": agent_reply})
    
    # Grade agent reply
    analysis_grade = agent_orchestrator.run_pipeline(history, msg0, agent_last_reply=agent_reply)
    print(f"Agent Evaluation Empathy: {analysis_grade['agent_evaluation']['empathy_score']}%")
    print(f"Agent Evaluation Critique: {analysis_grade['agent_evaluation']['critique']}")

    # Next Customer message
    msg1 = sim.get_next_customer_message(agent_response=agent_reply)
    print(f"Customer: {msg1}")
    history.append({"sender": "customer", "text": msg1})
    
    # Generate final report
    print("\nGenerating final report...")
    report = agent_orchestrator.generate_final_report(history, [analysis, analysis_grade])
    print(f"Report Title: {report['title']}")
    print(f"Quality Score: {report['resolution_quality_score']}")
    print(f"Recommendations: {report['recommendations']}")
    
    print("\nAll Backend Agent Pipeline tests completed successfully!")

if __name__ == "__main__":
    test_pipeline()