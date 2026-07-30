"""
Inspect each agent's output separately, or all together.

Usage (run from inside backend/):
    python test_agents_individual.py                 # runs ALL agents in sequence
    python test_agents_individual.py understanding    # just CustomerUnderstandingAgent
    python test_agents_individual.py knowledge        # just KnowledgeAgent (RAG)
    python test_agents_individual.py coaching         # just ResponseCoachingAgent
    python test_agents_individual.py quality          # just QualityMonitoringAgent

You can also edit CUSTOMER_MESSAGE / AGENT_REPLY below to test different scenarios.
"""
import sys
import os
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from backend.agents import agent_orchestrator, get_llm_client

SEPARATOR = "=" * 70

# Edit these to test different scenarios
CUSTOMER_MESSAGE = "I just saw a double charge of $29.99 on my Visa card! This is unacceptable, refund me now!"
AGENT_REPLY = "I understand you were charged twice. Can I get your email to process the refund?"


def pretty(label, data):
    print(f"\n{SEPARATOR}\n{label}\n{SEPARATOR}")
    print(json.dumps(data, indent=2, default=str))


def run_understanding(llm_client, history):
    result = agent_orchestrator.understanding_agent.analyze(
        CUSTOMER_MESSAGE, history, llm_client
    )
    pretty("1. CustomerUnderstandingAgent.analyze()", result)
    return result


def run_knowledge(intent):
    result = agent_orchestrator.knowledge_agent.retrieve(CUSTOMER_MESSAGE, intent)
    pretty("2. KnowledgeAgent.retrieve()", result)
    return result


def run_coaching(intent, sentiment, retrieved_docs, history, llm_client):
    no_reply = agent_orchestrator.coaching_agent.get_suggestions_and_coaching(
        message=CUSTOMER_MESSAGE,
        intent=intent,
        sentiment=sentiment,
        retrieved_docs=retrieved_docs,
        history=history,
        agent_last_reply=None,
        llm_client=llm_client,
    )
    pretty("3. ResponseCoachingAgent [no agent reply yet]", no_reply)

    with_reply = agent_orchestrator.coaching_agent.get_suggestions_and_coaching(
        message=CUSTOMER_MESSAGE,
        intent=intent,
        sentiment=sentiment,
        retrieved_docs=retrieved_docs,
        history=history + [{"sender": "agent", "text": AGENT_REPLY}],
        agent_last_reply=AGENT_REPLY,
        llm_client=llm_client,
    )
    pretty(f"3b. ResponseCoachingAgent [grading reply: '{AGENT_REPLY}']", with_reply)
    return with_reply


def run_quality(intent, sentiment, history, llm_client):
    result = agent_orchestrator.quality_agent.monitor(
        history=history + [{"sender": "agent", "text": AGENT_REPLY}],
        sentiment=sentiment,
        intent=intent,
        llm_client=llm_client,
    )
    pretty("4. QualityMonitoringAgent.monitor()", result)
    return result


def main():
    agent_choice = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    valid_choices = {"all", "understanding", "knowledge", "coaching", "quality"}

    if agent_choice not in valid_choices:
        print(f"Unknown agent '{agent_choice}'. Choose from: {', '.join(sorted(valid_choices))}")
        sys.exit(1)

    llm_client = get_llm_client()
    active_providers = [p['provider'] for p in llm_client['providers']] if llm_client else None
    print(f"LLM client active providers: {active_providers}")
    print(f"Running: {agent_choice}")

    history = [{"sender": "customer", "text": CUSTOMER_MESSAGE}]

    # Understanding is a dependency for knowledge/coaching/quality, so run it
    # quietly first (without printing) when testing those individually.
    if agent_choice == "understanding":
        run_understanding(llm_client, history)

    elif agent_choice == "knowledge":
        understanding = agent_orchestrator.understanding_agent.analyze(CUSTOMER_MESSAGE, history, llm_client)
        run_knowledge(understanding["intent"])

    elif agent_choice == "coaching":
        understanding = agent_orchestrator.understanding_agent.analyze(CUSTOMER_MESSAGE, history, llm_client)
        retrieved_docs = agent_orchestrator.knowledge_agent.retrieve(CUSTOMER_MESSAGE, understanding["intent"])
        run_coaching(understanding["intent"], understanding["sentiment"], retrieved_docs, history, llm_client)

    elif agent_choice == "quality":
        understanding = agent_orchestrator.understanding_agent.analyze(CUSTOMER_MESSAGE, history, llm_client)
        run_quality(understanding["intent"], understanding["sentiment"], history, llm_client)

    else:  # "all"
        understanding = run_understanding(llm_client, history)
        retrieved_docs = run_knowledge(understanding["intent"])
        run_coaching(understanding["intent"], understanding["sentiment"], retrieved_docs, history, llm_client)
        run_quality(understanding["intent"], understanding["sentiment"], history, llm_client)

    print(f"\n{SEPARATOR}\nDone.\n{SEPARATOR}")


if __name__ == "__main__":
    main()
