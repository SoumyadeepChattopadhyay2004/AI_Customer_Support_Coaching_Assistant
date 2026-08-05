import os
import re
import json
from typing import List, Dict, Any, Optional
from backend.rag import rag_engine

# LangChain: used for two things in this file --
# 1. `call_llm` / `get_llm_client` -- chat-model instantiation + automatic
#    provider failover (Groq -> Gemini -> OpenAI), replacing the hand-rolled
#    for-loop-over-providers that used to live here.
# 2. `AgentOrchestrator` -- the actual multi-agent *orchestration*: the four
#    agents are wired together as a declarative LCEL graph (Runnable chain)
#    instead of a straight-line sequence of Python calls, so independent
#    steps (Response Coaching + Quality Monitoring, which only depend on the
#    Understanding Agent's output, not on each other) execute concurrently.

from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough 
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI 

# Helper regex to extract emails or numbers
EMAIL_REGEX = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
ORDER_REGEX = re.compile(r'\b[A-Za-z0-9]{8,12}\b')


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------
# Each agent gets a dedicated system prompt (sent as the "system" role) so
# behavior/format rules are separated from the per-call task data.

UNDERSTANDING_SYSTEM_PROMPT = """## Role
You are the Customer Understanding Agent inside a real-time customer support coaching platform. You read the customer's latest message and turn it into structured signals (intent, sentiment, tone, entities) that downstream agents rely on.

## Tone
Analytical, neutral, and precise.

## Language
English only.

## Core Behavior
### ALWAYS DO:
- Base every label strictly on the customer's actual words and the provided chat history.
- Choose 'intent' from the closest matching category style already implied by examples (e.g. 'Billing & Refunds', 'Technical Support', 'Subscription Cancellation', 'General Inquiry'); use 'General Inquiry' if nothing else fits.
- Choose 'sentiment' as exactly one of: 'Angry', 'Frustrated', 'Neutral', 'Satisfied'.
- Extract entities (email, amount, etc.) only when explicitly present in the message text.
- Return every requested JSON key, using null or an empty array when a value is not applicable.

### NEVER DO:
- Do not add commentary, explanations, apologies, or markdown prose outside the JSON.
- Do not infer sentiment from assumptions beyond the message text itself.
- Do not fabricate entities (emails, amounts, order numbers) that are not present in the message.
- Do not invent new JSON keys or omit requested ones.

## Response Format Guidelines
- Respond with ONLY a raw JSON code block — no preamble, no closing remarks."""

COACHING_SYSTEM_PROMPT = """## Role
You are the Response Coaching Agent inside a real-time customer support coaching platform. Given the live conversation, detected intent/sentiment, and relevant knowledge base snippets, you draft response suggestions the human agent can send, coaching tips, and (when a reply was given) a grade of the agent's last reply.

## Tone
Supportive, constructive, and specific — like an experienced team lead coaching a newer agent in real time.

## Language
English only.

## Core Behavior
### ALWAYS DO:
- Ground every suggested response in the customer's actual message, detected intent/sentiment, and the supplied knowledge base context.
- Make suggestions distinct from one another (different style or strategy), not minor rewordings.
- Keep coaching tips actionable and specific to this conversation, not generic platitudes.
- When grading an agent's reply, base empathy_score and clarity_score on concrete elements present or missing (acknowledgment of feelings, clear next step, policy accuracy).
- Only include 'agent_evaluation' when an agent reply was actually provided.

### NEVER DO:
- Do not fabricate policy details, refund amounts, or timelines that are not present in the knowledge base context or conversation.
- Do not suggest responses that promise something outside standard support policy (e.g. unauthorized discounts) unless grounded in the retrieved knowledge.
- Do not add commentary outside the JSON.
- Do not pad the critique with praise alone if there are real issues — be honest and direct.

## Response Format Guidelines
- Respond with ONLY a raw JSON code block — no preamble, no closing remarks."""

QUALITY_SYSTEM_PROMPT = """## Role
You are the Quality Monitoring Agent inside a real-time customer support coaching platform. You watch the full conversation for escalation risk and score resolution quality so supervisors can intervene before a conversation goes wrong.

## Tone
Objective, risk-aware, and concise.

## Language
English only.

## Core Behavior
### ALWAYS DO:
- Base 'escalation_risk' on concrete signals in the chat history (explicit threats, repeated frustration, unresolved delays, requests for a supervisor/legal action).
- Justify the chosen risk level in 'escalation_reasoning' with a specific reference to what happened in the conversation.
- Recommend a concrete, actionable 'intervention_strategy' (or 'None' only when risk is genuinely Low).
- Score 'resolution_quality_score' (0-100) based on policy compliance, response speed, and empathy shown by the agent.
- Summarize the conversation factually in 'conversation_summary' — only what actually happened.

### NEVER DO:
- Do not escalate risk level without a concrete supporting reason from the transcript.
- Do not invent details not present in the chat history.
- Do not add commentary outside the JSON.

## Response Format Guidelines
- Respond with ONLY a raw JSON code block — no preamble, no closing remarks."""

REPORT_SYSTEM_PROMPT = """## Role
You are the Reporting Agent inside a real-time customer support coaching platform. After a conversation ends, you produce the structured post-interaction performance report a supervisor reviews.

## Tone
Professional, balanced, and evaluative — fair to the agent while being honest about weaknesses.

## Language
English only.

## Core Behavior
### ALWAYS DO:
- Base the report strictly on what occurred in the provided chat history and sentiment journey.
- Score each competency (empathy, clarity, policy_compliance, speed) from 0-100 based on evidence in the transcript.
- Write 'conversation_summary' as a factual 1-2 paragraph account of what happened and the outcome.
- Make 'recommendations' specific to this agent's actual performance in this conversation, not generic tips.

### NEVER DO:
- Do not fabricate events, quotes, or outcomes that are not in the transcript.
- Do not give uniformly perfect scores unless the transcript genuinely supports it.
- Do not add commentary outside the JSON.

## Response Format Guidelines
- Respond with ONLY a raw JSON code block — no preamble, no closing remarks."""

class CustomerUnderstandingAgent:
    """
    Analyzes the last customer message for:
    - Intent
    - Sentiment
    - Tone
    - Extracted Entities (email, order id, phone)
    """
    def analyze(self, message: str, history: List[Dict[str, str]], llm_client: Optional[Any] = None) -> Dict[str, Any]:
        if llm_client:
            return self._analyze_llm(message, history, llm_client)
        else:
            result = self._analyze_mock(message)
            result["_source"] = "mock"
            return result

    def _analyze_mock(self, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        
        # Intent Detection
        intent = "General Inquiry"
        if any(w in msg_lower for w in ["charge", "billing", "double", "money", "price", "card", "refund", "cost"]):
            intent = "Billing & Refunds"
        elif any(w in msg_lower for w in ["router", "internet", "wifi", "connect", "slow", "down", "red light", "reset"]):
            intent = "Technical Support"
        elif any(w in msg_lower for w in ["cancel", "unsubscribe", "stop", "close account", "billing cycle"]):
            intent = "Subscription Cancellation"

        # Sentiment Analysis
        sentiment = "Neutral"
        if any(w in msg_lower for w in ["ridiculous", "unacceptable", "furious", "angry", "terrible", "raising prices", "sue", "legal"]):
            sentiment = "Angry"
        elif any(w in msg_lower for w in ["stress", "stressful", "worry", "miss", "urgency", "hurry", "impatient", "please help"]):
            sentiment = "Frustrated"
        elif any(w in msg_lower for w in ["thanks", "thank you", "great", "awesome", "perfect", "appreciate"]):
            sentiment = "Satisfied"

        # Tone Detection
        tones = []
        if sentiment == "Angry":
            tones.append("Hostile")
        if sentiment == "Frustrated":
            tones.append("Anxious/Impatient")
        if sentiment == "Satisfied" or "please" in msg_lower:
            tones.append("Polite")
        if not tones:
            tones.append("Neutral")

        # Entity Extraction
        emails = EMAIL_REGEX.findall(message)
        email = emails[0] if emails else None
        
        return {
            "intent": intent,
            "sentiment": sentiment,
            "tones": tones,
            "entities": {
                "email": email,
                "amount": "$29.99" if "double charge" in msg_lower or "subscription" in msg_lower else None
            }
        }

    def _analyze_llm(self, message: str, history: List[Dict[str, str]], llm_client: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            f"Customer's latest message: \"{message}\"\n\n"
            f"Provide a JSON response with the following keys:\n"
            f"1. 'intent': (e.g. 'Billing & Refunds', 'Technical Support', 'Subscription Cancellation', 'General Inquiry')\n"
            f"2. 'sentiment': (one of: 'Angry', 'Frustrated', 'Neutral', 'Satisfied')\n"
            f"3. 'tones': array of descriptive tone tags (e.g. ['Aggressive', 'Anxious', 'Polite', 'Direct'])\n"
            f"4. 'entities': object with keys 'email' and 'amount' representing any parsed emails or monetary details."
        )
        try:
            raw_response = call_llm(prompt, llm_client, system_prompt=UNDERSTANDING_SYSTEM_PROMPT)
            result = json.loads(extract_json_block(raw_response))
            result["_source"] = "llm"
            return result
        except Exception as e:
            print(f"Error in CustomerUnderstandingAgent LLM call, falling back to mock: {e}")
            result = self._analyze_mock(message)
            result["_source"] = "mock"
            return result


class KnowledgeAgent:
    """
    RAG-powered Knowledge Base Retriever.
    Searches documents and FAQs.
    """
    # Maps a detected customer intent to the KB categories that are actually
    # relevant to it. Raw text/embedding similarity alone can be misled by
    # incidental overlap -- e.g. "how long will this refund take" and "how
    # long does shipping take" are semantically close in phrasing even
    # though one is Billing & Refunds and the other is Shipping & Delivery.
    # This map lets retrieve() prefer same-category articles instead of
    # trusting raw similarity score alone.
    INTENT_CATEGORY_MAP: Dict[str, List[str]] = {
        "Billing & Refunds": ["Billing & Refunds"],
        "Technical Support": ["Technical Support"],
        "Subscription Cancellation": ["Billing & Refunds"],
        # "General Inquiry" intentionally has no mapping -- fall back to
        # raw similarity ranking since there's no category to bias toward.
    }

    def retrieve(self, message: str, intent: str) -> List[Dict[str, Any]]:
        query = f"{intent} {message}"
        preferred_categories = self.INTENT_CATEGORY_MAP.get(intent, [])

        # Pull more candidates than we need so there's something to
        # re-rank from, not just whatever the raw top_k happened to be.
        candidates = rag_engine.retrieve(query, top_k=6)

        if preferred_categories:
            candidates.sort(
                key=lambda d: (
                    0 if d.get("category") in preferred_categories else 1,
                    -(d.get("relevance_score") or 0.0)
                )
            )

        return candidates[:2]


class ResponseCoachingAgent:
    """
    Generates response suggestions and evaluates agent replies for tone & clarity.
    """
    def get_suggestions_and_coaching(
        self, 
        message: str, 
        intent: str, 
        sentiment: str, 
        retrieved_docs: List[Dict[str, Any]], 
        history: List[Dict[str, str]],
        agent_last_reply: Optional[str] = None,
        llm_client: Optional[Any] = None
    ) -> Dict[str, Any]:
        if llm_client:
            return self._get_llm(message, intent, sentiment, retrieved_docs, history, agent_last_reply, llm_client)
        else:
            result = self._get_mock(message, intent, sentiment, retrieved_docs, agent_last_reply)
            result["_source"] = "mock"
            return result

    def _get_mock(self, message: str, intent: str, sentiment: str, retrieved_docs: List[Dict[str, Any]], agent_last_reply: Optional[str] = None) -> Dict[str, Any]:
        # Pre-baked suggestions based on intent
        suggestions = []
        coaching_tips = [
            "Acknowledge the customer's sentiment immediately using active listening.",
            "Explain the technical/billing background before requesting action or processing modifications."
        ]

        if intent == "Billing & Refunds":
            suggestions = [
                {
                    "type": "Empathetic & Helpful",
                    "text": "I understand how concerning double charges can be, and I apologize for the inconvenience. Let me find your account using your email jerry.billing@example.com right away and reverse the duplicate transaction.",
                    "rationale": "Directly addresses their concern and outlines a clear path to resolution."
                },
                {
                    "type": "Direct & Professional",
                    "text": "I can certainly assist in refunding the duplicate charge. To get started, could you verify the email address linked to your account and the transaction dates?",
                    "rationale": "Slightly more formal, ideal for verifying credentials first."
                }
            ]
            coaching_tips = [
                "Always verify the account details before processing refunds to maintain compliance.",
                "Empathize with their budget concerns: duplicate charges create temporary holds that affect their balance.",
                "Remind the customer of bank processing times (3-5 days) to manage expectation levels."
            ]
        elif intent == "Technical Support":
            suggestions = [
                {
                    "type": "Empathetic & Troubleshooting",
                    "text": "I know how stressful it is to have your internet drop right before a meeting. Let's start by power cycling your router: unplug the power cord for 30 seconds, then plug it back in. Let me know what light is showing.",
                    "rationale": "Shows urgency and breaks down the first troubleshooting step clearly."
                },
                {
                    "type": "Direct & Action-Oriented",
                    "text": "A flashing red light means the router cannot establish a connection. Please hold down the 'Reset' pinhole button on the back for 15 seconds to perform a factory reset.",
                    "rationale": "Clear directive steps for resolving router issues."
                }
            ]
            coaching_tips = [
                "Validate the impact of the outage (e.g. work meeting) to show the customer you care.",
                "Ensure steps are single-threaded so the customer doesn't get overwhelmed.",
                "Mention default Wi-Fi settings will restore, meaning they will need the SSID on the router base."
            ]
        elif intent == "Subscription Cancellation":
            suggestions = [
                {
                    "type": "Retention Offer",
                    "text": "I understand that cost is a factor, and we'd hate to lose you. I can downgrade your plan to our $9/month Starter package, or offer your next month completely free. Would either of these help?",
                    "rationale": "Follows the save protocol by offering cheaper alternatives first."
                },
                {
                    "type": "Polite Cancellation Processing",
                    "text": "I can process this cancellation for you right away. Your premium benefits will remain active until the end of the current billing cycle, and you won't see any further charges.",
                    "rationale": "Acknowledges their request and outlines clear parameters for cancellation."
                }
            ]
            coaching_tips = [
                "Always attempt to save the subscription once using a discount or downgrade option before cancelling.",
                "Confirm that no cancellation fees apply and outline the end date of their current cycle."
            ]
        else:
            suggestions = [
                {
                    "type": "Standard Professional",
                    "text": "Thank you for reaching out. I'd be happy to help you with this. Could you please provide your order or account number?",
                    "rationale": "Universal opening response."
                },
                {
                    "type": "Short & Direct",
                    "text": "I can help with that. Can you tell me a little more about the issue you are experiencing?",
                    "rationale": "Simple open-ended prompt."
                }
            ]

        # Analyze agent's last reply if available
        agent_evaluation = None
        if agent_last_reply:
            reply_lower = agent_last_reply.lower()
            empathy = 80
            clarity = 85
            
            # Simple keyword checks to grade the agent
            critiques = []
            if not any(w in reply_lower for w in ["sorry", "apologize", "understand", "concern", "stress"]):
                empathy -= 30
                critiques.append("Try starting with a brief expression of empathy (e.g. 'I apologize for the trouble').")
            if any(w in reply_lower for w in ["system bug", "our error", "bad code", "broken server"]):
                critiques.append("Avoid attributing issues to internal system errors or placing blame.")
            if "?" not in agent_last_reply and not any(w in reply_lower for w in ["unplug", "reset", "provide", "give", "verify"]):
                clarity -= 15
                critiques.append("Ensure your message ends with a clear question or a specific next step.")

            if empathy < 70:
                critique_text = "Empathy score is low. " + " ".join(critiques)
            elif critiques:
                critique_text = "Good structure. " + " ".join(critiques)
            else:
                critique_text = "Excellent reply! Empathy and clarity are well balanced."

            agent_evaluation = {
                "empathy_score": max(20, empathy),
                "clarity_score": max(20, clarity),
                "critique": critique_text
            }

        return {
            "suggestions": suggestions,
            "coaching_tips": coaching_tips,
            "agent_evaluation": agent_evaluation
        }

    def _get_llm(
        self,
        message: str,
        intent: str,
        sentiment: str,
        retrieved_docs: List[Dict[str, Any]],
        history: List[Dict[str, str]],
        agent_last_reply: Optional[str],
        llm_client: Dict[str, Any]
    ) -> Dict[str, Any]:
        docs_context = "\n".join([f"- {d['title']}: {d['content']}" for d in retrieved_docs])
        history_str = ""
        for turn in history:
            history_str += f"{turn['sender'].capitalize()}: {turn['text']}\n"

        prompt = (
            f"Customer last message: \"{message}\"\n"
            f"Detected Intent: {intent}\n"
            f"Detected Sentiment: {sentiment}\n"
            f"Relevant Knowledge Docs:\n{docs_context}\n\n"
            f"Chat History:\n{history_str}\n"
        )
        
        if agent_last_reply:
            prompt += f"Agent's last reply: \"{agent_last_reply}\"\n"

        prompt += (
            f"Provide a JSON response with the following keys:\n"
            f"1. 'suggestions': List of 2 objects, each containing 'type' (e.g. 'Empathetic Response'), 'text' (suggested text to send), and 'rationale' (brief note on why this works).\n"
            f"2. 'coaching_tips': List of 2-3 coaching pointers/best practices for the agent given the customer's state.\n"
            f"3. 'agent_evaluation': (Required only if agent's last reply was provided) Object with 'empathy_score' (0-100), 'clarity_score' (0-100), and 'critique' (brief assessment with actionable advice)."
        )

        try:
            raw_response = call_llm(prompt, llm_client, system_prompt=COACHING_SYSTEM_PROMPT)
            parsed = json.loads(extract_json_block(raw_response))
            # The LLM only includes 'agent_evaluation' when an agent reply was
            # provided; make sure the key always exists downstream regardless.
            parsed.setdefault("agent_evaluation", None)
            parsed["_source"] = "llm"
            return parsed
        except Exception as e:
            print(f"Error in ResponseCoachingAgent LLM call: {e}")
            result = self._get_mock(message, intent, sentiment, retrieved_docs, agent_last_reply)
            result["_source"] = "mock"
            return result


class QualityMonitoringAgent:
    """
    Monitors conversations for escalation risk, gives reasoning, recommendations,
    maintains summaries, and grades resolution quality.
    """
    def monitor(
        self, 
        history: List[Dict[str, str]], 
        sentiment: str, 
        intent: str, 
        llm_client: Optional[Any] = None
    ) -> Dict[str, Any]:
        if llm_client:
            return self._monitor_llm(history, sentiment, intent, llm_client)
        else:
            result = self._monitor_mock(history, sentiment, intent)
            result["_source"] = "mock"
            return result

    def _monitor_mock(self, history: List[Dict[str, str]], sentiment: str, intent: str) -> Dict[str, Any]:
        escalation_risk = "Low"
        reasoning = "Conversation is proceeding standardly."
        intervention = "Continue standard guidance."
        quality_score = 90

        # Check for angry customer or negative indicators
        customer_msgs = [m["text"] for m in history if m["sender"] == "customer"]
        agent_msgs = [m["text"] for m in history if m["sender"] == "agent"]
        
        last_customer_msg = customer_msgs[-1].lower() if customer_msgs else ""
        
        # Simple risk modeling
        if sentiment == "Angry":
            escalation_risk = "High"
            reasoning = "Customer is highly agitated and showing intense frustration with billing/system errors."
            intervention = "Express sincere apology, waive additional fees, or offer to escalate to supervisor immediately."
            quality_score = 65
        elif sentiment == "Frustrated":
            escalation_risk = "Medium"
            reasoning = "Customer is experiencing frustration due to delays or confusion."
            intervention = "Reassure customer of step-by-step resolution, provide estimated wait/processing times."
            quality_score = 78

        # Keyword based high risk triggers
        if any(w in last_customer_msg for w in ["supervisor", "manager", "legal", "sue", "chargeback", "cancel subscription", "terrible support"]):
            escalation_risk = "High"
            reasoning = "Customer threatened a cancellation, legal action, or requested supervisor escalation."
            intervention = "Immediately offer standard supervisor transfer options or apply authorized credit/retention plan."
            quality_score = 50

        # Adjust score based on length of conversation
        if len(history) > 6 and escalation_risk != "Low":
            quality_score = max(30, quality_score - 10)

        # Simple summarizer
        summary_bullets = []
        if intent == "Billing & Refunds":
            summary_bullets = [
                "Customer reported duplicate credit card charge of $29.99.",
                "Agent verified transaction history and spotted pending authorization.",
                "Refund for duplicate charge initiated."
            ]
        elif intent == "Technical Support":
            summary_bullets = [
                "Customer reported Aura Router offline with flashing red light.",
                "Agent guided power cycle, which did not resolve connection issue.",
                "Factory reset successfully performed and router online."
            ]
        elif intent == "Subscription Cancellation":
            summary_bullets = [
                "Customer requested cancellation due to budget constraints.",
                "Agent offered retention alternatives.",
                "Subscription scheduled for cancellation at the billing cycle close."
            ]
        else:
            summary_bullets = ["Customer started conversation.", "Support agent responding to query."]

        return {
            "escalation_risk": escalation_risk,
            "escalation_reasoning": reasoning,
            "intervention_strategy": intervention,
            "resolution_quality_score": quality_score,
            "conversation_summary": summary_bullets
        }

    def _monitor_llm(self, history: List[Dict[str, str]], sentiment: str, intent: str, llm_client: Dict[str, Any]) -> Dict[str, Any]:
        history_str = ""
        for turn in history:
            history_str += f"{turn['sender'].capitalize()}: {turn['text']}\n"

        prompt = (
            f"Chat History:\n{history_str}\n"
            f"Detected intent: {intent}\n"
            f"Last sentiment: {sentiment}\n\n"
            f"Provide a JSON response with the following keys:\n"
            f"1. 'escalation_risk': 'Low', 'Medium', or 'High'\n"
            f"2. 'escalation_reasoning': brief explanation of why this risk level was selected.\n"
            f"3. 'intervention_strategy': recommended action to prevent escalation (or 'None' if Low risk).\n"
            f"4. 'resolution_quality_score': an integer from 0 to 100 based on policy compliance, speed, and empathy.\n"
            f"5. 'conversation_summary': list of 2-3 bullet points summarizing what occurred."
        )

        try:
            raw_response = call_llm(prompt, llm_client, system_prompt=QUALITY_SYSTEM_PROMPT)
            result = json.loads(extract_json_block(raw_response))
            result["_source"] = "llm"
            return result
        except Exception as e:
            print(f"Error in QualityMonitoringAgent LLM call: {e}")
            result = self._monitor_mock(history, sentiment, intent)
            result["_source"] = "mock"
            return result


# Orchestrator to coordinate the pipeline
class AgentOrchestrator:
    """
    Wires the four specialist agents together into a single pipeline using
    LangChain's LCEL (`Runnable`) primitives instead of a hand-written
    sequence of Python method calls.

    Pipeline shape:

        understand  -->  retrieve (RAG)  -->  { coach, monitor } (parallel)  -->  merge

    - `understand` and `retrieve` are inherently sequential: retrieval needs
      the detected intent.
    - `coach` (ResponseCoachingAgent) and `monitor` (QualityMonitoringAgent)
      each only depend on the understanding + history/docs already computed,
      not on each other's output, so they're expressed with
      `RunnablePassthrough.assign(...)`. LCEL runs the keys assigned that
      way concurrently (via a thread pool for sync `.invoke()`), which means
      the two LLM calls actually happen in parallel instead of back-to-back
      as in the original implementation -- a real orchestration win, not
      just a refactor.
    """

    def __init__(self):
        self.understanding_agent = CustomerUnderstandingAgent()
        self.knowledge_agent = KnowledgeAgent()
        self.coaching_agent = ResponseCoachingAgent()
        self.quality_agent = QualityMonitoringAgent()
        self.pipeline: Runnable = self._build_pipeline()

    def _build_pipeline(self) -> Runnable:
        understand_step = RunnableLambda(
            lambda x: {
                **x,
                "understanding": self.understanding_agent.analyze(
                    x["message"], x["history"], x["llm_client"]
                ),
            }
        ).with_config({"run_name": "understand_customer"})

        retrieve_step = RunnableLambda(
            lambda x: {
                **x,
                "retrieved_docs": self.knowledge_agent.retrieve(
                    x["message"], x["understanding"]["intent"]
                ),
            }
        ).with_config({"run_name": "retrieve_knowledge"})

        # RunnablePassthrough.assign keeps every existing key on the input
        # dict (message, history, llm_client, understanding, retrieved_docs,
        # ...) while adding "coaching" and "quality", computing both
        # concurrently since neither depends on the other.
        coach_and_monitor_step = RunnablePassthrough.assign(
            coaching=RunnableLambda(
                lambda x: self.coaching_agent.get_suggestions_and_coaching(
                    message=x["message"],
                    intent=x["understanding"]["intent"],
                    sentiment=x["understanding"]["sentiment"],
                    retrieved_docs=x["retrieved_docs"],
                    history=x["history"],
                    agent_last_reply=x.get("agent_last_reply"),
                    llm_client=x["llm_client"],
                )
            ),
            quality=RunnableLambda(
                lambda x: self.quality_agent.monitor(
                    history=x["history"],
                    sentiment=x["understanding"]["sentiment"],
                    intent=x["understanding"]["intent"],
                    llm_client=x["llm_client"],
                )
            ),
        ).with_config({"run_name": "coach_and_monitor_parallel"})

        merge_step = RunnableLambda(self._merge_results).with_config({"run_name": "merge_results"})

        return understand_step | retrieve_step | coach_and_monitor_step | merge_step

    def _merge_results(self, x: Dict[str, Any]) -> Dict[str, Any]:
        understanding, retrieved_docs = x["understanding"], x["retrieved_docs"]
        coaching, quality = x["coaching"], x["quality"]

        ai_sources = {
            "understanding": understanding.get("_source", "mock"),
            "coaching": coaching.get("_source", "mock"),
            "quality": quality.get("_source", "mock"),
        }
        return {
            "intent": understanding["intent"],
            "sentiment": understanding["sentiment"],
            "tones": understanding["tones"],
            "entities": understanding["entities"],
            "retrieved_documents": retrieved_docs,
            "suggestions": coaching["suggestions"],
            "coaching_tips": coaching["coaching_tips"],
            "agent_evaluation": coaching.get("agent_evaluation"),
            "escalation_risk": quality["escalation_risk"],
            "escalation_reasoning": quality["escalation_reasoning"],
            "intervention_strategy": quality["intervention_strategy"],
            "resolution_quality_score": quality["resolution_quality_score"],
            "conversation_summary": quality["conversation_summary"],
            # True only when every stage actually got a response from the LLM
            # (not a silent fallback). Lets the UI show whether what's on
            # screen is AI-generated or the deterministic mock logic.
            "ai_generated": all(v == "llm" for v in ai_sources.values()),
            "ai_sources": ai_sources,
        }

    def run_pipeline(self, history: List[Dict[str, str]], last_customer_message: str, agent_last_reply: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs the full coaching pipeline (LCEL graph built in __init__).
        Returns a single frame matching CoachingResponse structure -- same
        return shape as before, only the wiring underneath changed.
        """
        inputs = {
            "message": last_customer_message,
            "history": history,
            "agent_last_reply": agent_last_reply,
            # Determine if LLM keys are configured (per-call, same as before,
            # since env vars / mock-mode can change between calls in tests).
            "llm_client": get_llm_client(),
        }
        return self.pipeline.invoke(inputs)

    def generate_final_report(self, history: List[Dict[str, str]], analysis_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates the structured post-interaction report.
        """
        llm_client = get_llm_client()
        
        # Analyze sentiment journey
        sentiment_journey = [a["sentiment"] for a in analysis_history]
        
        # Compute final resolution quality score
        if analysis_history:
            final_quality = int(sum(a["resolution_quality_score"] for a in analysis_history) / len(analysis_history))
        else:
            final_quality = 80

        # Construct final summary and recommendations
        if llm_client:
            return self._generate_report_llm(history, sentiment_journey, final_quality, llm_client)
        else:
            return self._generate_report_mock(history, sentiment_journey, final_quality)

    def _generate_report_mock(self, history: List[Dict[str, str]], sentiment_journey: List[str], final_quality: int) -> Dict[str, Any]:
        # Determine scenario based on customer texts
        cust_texts = " ".join([m["text"].lower() for m in history if m["sender"] == "customer"])
        
        competencies = {
            "empathy": 85,
            "clarity": 90,
            "policy_compliance": 95,
            "speed": 88
        }
        
        recommendations = [
            "Good work maintaining active listening! Keep reinforcing the customer's sentiment early.",
            "Make sure to state bank transit timelines or setup terms in bold points for customer readability."
        ]

        if "router" in cust_texts or "wifi" in cust_texts:
            title = "Aura Router Support Evaluation"
            summary = "The agent successfully diagnosed the Aura router outage and assisted the customer in resolving the connection using factory reset protocols before their work meeting."
        elif "charge" in cust_texts or "billing" in cust_texts:
            title = "Billing Double Charge Resolution Evaluation"
            summary = "The agent verified the double charge against the active statement logs, confirmed a duplicate hold, and initiated a standard bank refund with appropriate customer empathy."
            competencies["policy_compliance"] = 100
        else:
            title = "Customer Support Session Evaluation"
            summary = "The agent resolved the customer query within an acceptable number of turns, aligning with standard SLA policies."

        # Create structured report
        return {
            "title": title,
            "resolution_quality_score": final_quality,
            "sentiment_journey": sentiment_journey,
            "competencies": competencies,
            "conversation_summary": summary,
            "recommendations": recommendations
        }

    def _generate_report_llm(self, history: List[Dict[str, str]], sentiment_journey: List[str], final_quality: int, llm_client: Dict[str, Any]) -> Dict[str, Any]:
        history_str = ""
        for turn in history:
            history_str += f"{turn['sender'].capitalize()}: {turn['text']}\n"

        prompt = (
            f"Chat History:\n{history_str}\n"
            f"Sentiment Journey History: {sentiment_journey}\n"
            f"Calculated Quality Score: {final_quality}\n\n"
            f"Provide a JSON response with the following keys:\n"
            f"1. 'title': A summary title (e.g. 'Billing Refund Review')\n"
            f"2. 'resolution_quality_score': final score (0-100)\n"
            f"3. 'sentiment_journey': array of strings matching the input sentiment list.\n"
            f"4. 'competencies': object with keys 'empathy', 'clarity', 'policy_compliance', 'speed', scoring each from 0 to 100.\n"
            f"5. 'conversation_summary': 1-2 paragraph description of what occurred, how it was handled, and the outcome.\n"
            f"6. 'recommendations': array of 2-3 personalized improvement tips for this specific agent."
        )

        try:
            raw_response = call_llm(prompt, llm_client, system_prompt=REPORT_SYSTEM_PROMPT)
            return json.loads(extract_json_block(raw_response))
        except Exception as e:
            print(f"Error in generating LLM report: {e}")
            return self._generate_report_mock(history, sentiment_journey, final_quality)


# Helper functions for LLM calls
#
# Provider failover chain: Groq -> Gemini -> OpenAI. All three expose an
# OpenAI-compatible /v1 chat completions endpoint, so the same `openai` SDK
# client works for all of them -- just a different base_url/key/model per
# provider. Whichever env vars are set (in backend/.env) become part of the
# chain, in priority order. If one provider rate-limits or errors out,
# call_llm() automatically retries the next configured provider before
# giving up and letting the caller fall back to mock logic.
#
# Rationale for the ordering:
# - Groq: fastest, but smallest free daily token budget (~100K TPD on
#   llama-3.3-70b-versatile) -- good default, exhausts first.
# - Gemini: generous free daily request quota (1M tokens/day), good second option.
# - OpenAI: free trial credits only (no ongoing free tier) -- last resort.

_PROVIDER_DEFAULTS = {
    "groq": {
        "env_key": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.0-flash",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
    },
}

class LLMClient:
    """
    Thin wrapper around a LangChain chat-model `Runnable`. The runnable
    itself is `primary.with_fallbacks([fallback_1, fallback_2, ...])`, so
    provider failover (Groq -> Gemini -> OpenAI) is handled natively by
    LangChain: if the primary provider raises, LangChain automatically
    retries with the next one in the list before giving up.

    `provider_names` is kept only as introspection metadata (e.g. for
    test_agents_individual.py to print which providers are active); it
    plays no role in the actual failover, which happens inside `runnable`.
    """
    def __init__(self, runnable: Runnable, provider_names: List[str]):
        self.runnable = runnable
        self.provider_names = provider_names

    def invoke(self, messages: List[Any]) -> str:
        return self.runnable.invoke(messages).content


def get_llm_client() -> Optional[LLMClient]:
    """
    Builds a LangChain chat model (with `.with_fallbacks()` chaining across
    whichever providers are configured via env vars, Groq -> Gemini ->
    OpenAI). Returns None if no provider is configured at all (mock mode).
    """
    models: List[ChatOpenAI] = []
    provider_names: List[str] = []

    for name, cfg in _PROVIDER_DEFAULTS.items():
        key = os.getenv(cfg["env_key"])
        if not key:
            continue
        models.append(
            ChatOpenAI(
                api_key=key,
                base_url=cfg["base_url"],
                model=os.getenv(cfg["model_env"], cfg["default_model"]),
                temperature=0.2,
                max_retries=0,  # no per-provider retries -- fail fast onto the next provider
                timeout=30,
            ).with_config({"run_name": f"llm:{name}"})
        )
        provider_names.append(name)

    if not models:
        return None

    primary, *fallbacks = models
    runnable = primary.with_fallbacks(fallbacks) if fallbacks else primary
    return LLMClient(runnable, provider_names)

def call_llm(prompt: str, client: LLMClient, system_prompt: Optional[str] = None) -> str:
    if client is None:
        raise RuntimeError("No LLM providers configured")

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    return client.invoke(messages).strip()

def extract_json_block(text: str) -> str:
    # Extracts code block if wrapped in markdown
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

agent_orchestrator = AgentOrchestrator()
