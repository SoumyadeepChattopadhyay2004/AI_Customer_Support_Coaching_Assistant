import os
import random
from typing import List, Dict, Any

# Mock databases for the simulation fallback when LLM keys are not configured
MOCK_SIMULATOR_SCENARIOS = {
    "Billing Dispute": {
        "description": "Customer is disputing a double charge of $29.99 on their visa card.",
        "turns": [
            {
                "trigger_keywords": [],
                "Angry": "Hi, I just saw a double charge of $29.99 on my visa card statement! I need this refunded immediately. This is completely unacceptable!",
                "Confused": "Hello, I looked at my card statement and see two charges of $29.99. Did I subscribe twice by mistake? Can you please check?",
                "Impatient": "I have two charges of $29.99 on July 10th. I need you to refund one right now, I don't have time to wait in a queue.",
                "Polite": "Hi there! I noticed a double charge of $29.99 on my account. Could you please help me refund the second charge? Thank you!"
            },
            {
                "trigger_keywords": ["email", "order", "account", "details", "number", "identify"],
                "Angry": "Fine! My email is jerry.billing@example.com and the card was charged on July 10th. Do you need anything else to fix your system's mistake?",
                "Confused": "Oh, sorry. The email is jerry.billing@example.com. I don't have an order number, I just saw it on my bank statement.",
                "Impatient": "My email is jerry.billing@example.com. I don't have an order number. Just look up my email, please hurry up.",
                "Polite": "Sure! My email address is jerry.billing@example.com. Please let me know if you need any other details."
            },
            {
                "trigger_keywords": ["refund", "process", "reverse", "initiated", "back", "cancel", "charge"],
                "Angry": "It's about time. How long is this refund going to take to show up on my card? I hope it's instant.",
                "Confused": "Okay, thank you. So what was the second charge for? Was it a system bug? And when will it go back to my card?",
                "Impatient": "Okay, processed. How long until it is actually back in my bank? I need the funds immediately.",
                "Polite": "That is wonderful, thank you so much! How long does it usually take for the refund to reflect on my bank statement?"
            },
            {
                "trigger_keywords": ["business days", "days", "bank", "week", "time", "processed"],
                "Angry": "3 to 5 business days? That's way too slow! But whatever, as long as it's done. Make sure it's refunded.",
                "Confused": "Ah, okay, 3 to 5 days. I understand, banks can be slow. Thanks for clearing that up and fixing it.",
                "Impatient": "Ugh, 3-5 days. Fine. I guess I have no choice. Thanks.",
                "Polite": "I understand. Thank you so much for your quick and friendly assistance today! Have a great day!"
            }
        ]
    },
    "Technical Issue": {
        "description": "Customer's Aura Router is flashing red and they cannot connect to their work VPN.",
        "turns": [
            {
                "trigger_keywords": [],
                "Angry": "My internet is completely down and the router has a flashing red light! I'm going to miss an important client meeting in 10 minutes. Fix this now!",
                "Confused": "Hello, my internet stopped working. There's a little red light blinking on the modem box. What does that mean?",
                "Impatient": "Internet is down. Red light flashing on router. I have a presentation starting in a few minutes, help me get back online.",
                "Polite": "Hi! My internet seems to have disconnected. The Aura router has a blinking red light on the front panel. Could you help me troubleshoot?"
            },
            {
                "trigger_keywords": ["unplug", "reboot", "power", "cycle", "seconds", "turn off", "restart"],
                "Angry": "I already tried restarting it, but fine, I'll do it again. I unplugged it... Okay, I plugged it back in. It's booting up. It's still blinking red! This is useless!",
                "Confused": "Okay, let me find the power cable. I unplugged it... waiting... okay, plugged it back in. The lights are blinking. Now it's back to flashing red. What's next?",
                "Impatient": "Okay, power cycled it. Still blinking red. Let's move to the next step, I don't have time for basic diagnostics.",
                "Polite": "Okay, I have unplugged the power cable. I will wait for 30 seconds... Okay, plugging it back in now. The lights are cycling. Oh, it has returned to the flashing red light."
            },
            {
                "trigger_keywords": ["reset", "factory", "button", "pin", "hole", "back", "seconds", "paperclip"],
                "Angry": "A factory reset? Will that delete my settings? Whatever, I'm pressing the reset button on the back with a paperclip. 1... 5... 15. The light turned white. Now it's booting.",
                "Confused": "A factory reset button? Ah, I see a tiny hole on the back that says 'Reset'. Let me find a pen. Okay, I'm holding it down. The lights went off and now it's blinking white.",
                "Impatient": "Resetting it now. Holding the pinhole button. It's rebooting. Blinking white now. What do I do next?",
                "Polite": "Understood. I have a paperclip here. I am pressing the Reset button inside the pinhole for 15 seconds. The light has turned white, indicating it is resetting."
            },
            {
                "trigger_keywords": ["app", "reconfigure", "ssid", "setup", "green", "online", "connected"],
                "Angry": "Wait, the light just turned solid green! And my laptop reconnected. I have my meeting now, goodbye.",
                "Confused": "Oh, the light turned solid green! And my phone is back on the wifi. Do I still need to configure the app? Or is it all working?",
                "Impatient": "Green light is on. Connection is back. I'm joining my meeting now. Thanks.",
                "Polite": "Success! The light has turned solid green and my devices are reconnecting. The connection is stable. Thank you so much for the clear instructions!"
            }
        ]
    },
    "Subscription Save": {
        "description": "Customer wants to cancel their Premium Subscription because they find it too expensive.",
        "turns": [
            {
                "trigger_keywords": [],
                "Angry": "I want to cancel my premium subscription immediately. You guys keep raising prices and it's not worth the money!",
                "Confused": "Hi, I'm looking at my budget and need to cancel my subscription. It's just too expensive for me right now. How do I do that?",
                "Impatient": "Need to cancel my plan. Stop billing me. Let me know when it's done.",
                "Polite": "Hello! I would like to request a cancellation of my premium subscription. It has been great, but it's currently outside my budget. Thanks!"
            },
            {
                "trigger_keywords": ["discount", "free", "offer", "month", "save", "starter", "package", "cheap", "reduce", "deal"],
                "Angry": "I don't care about a discount or a free month. I want to cancel. Period. Stop trying to upsell me and cancel the account!",
                "Confused": "Oh, a free month or a $9 plan? That's nice, but I really don't use it enough to justify even $9. I think it's better to just cancel it for now.",
                "Impatient": "No offers. Just cancel it. I don't want any starter plan.",
                "Polite": "That is a very kind offer, thank you! However, I won't be using the service at all in the coming months, so I would still prefer to proceed with the cancellation."
            },
            {
                "trigger_keywords": ["cancel", "cancelled", "confirm", "stop", "billing", "refund", "effective"],
                "Angry": "Fine. Make sure I don't see any more charges on my card, or I'll dispute them with my bank.",
                "Confused": "Okay, so it will remain active until the end of the month? That works. Thank you for making this process easy.",
                "Impatient": "Is it cancelled? Send me the confirmation email. Thanks.",
                "Polite": "Thank you for processing that. I appreciate that there are no cancelation fees. Have a wonderful day!"
            }
        ]
    }
}

class CustomerSimulator:
    def __init__(self, scenario: str, personality: str):
        self.scenario = scenario if scenario in MOCK_SIMULATOR_SCENARIOS else "Billing Dispute"
        self.personality = personality if personality in ["Angry", "Confused", "Impatient", "Polite"] else "Polite"
        self.turn_index = 0
        self.conversation_history: List[Dict[str, str]] = []

    def get_next_customer_message(self, agent_response: str = None) -> str:
        """
        Generates the next customer message.
        If agent_response is provided, we append it to history first.
        Uses Groq, Gemini, or OpenAI (whichever key is present, in that order),
        otherwise falls back to pre-baked dialog turns.
        """
        if agent_response:
            self.conversation_history.append({"role": "agent", "content": agent_response})
            self.turn_index += 1

        # Check for LLM key -- only Groq, Gemini, and OpenAI (all offer free tiers) are supported
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if groq_key:
            return self._generate_llm_response(groq_key, provider="groq")
        elif gemini_key:
            return self._generate_llm_response(gemini_key, provider="gemini")
        elif openai_key:
            return self._generate_llm_response(openai_key, provider="openai")
        else:
            return self._generate_mock_response(agent_response)

    def _generate_mock_response(self, agent_response: str) -> str:
        scenario_data = MOCK_SIMULATOR_SCENARIOS[self.scenario]
        turns = scenario_data["turns"]

        # If we exceeded the mock turns, return a concluding message
        if self.turn_index >= len(turns):
            concluding_messages = {
                "Angry": "I'm done here. Goodbye.",
                "Confused": "Okay, that is all I needed. Thank you for your help.",
                "Impatient": "Got it. Bye.",
                "Polite": "Thank you so much! Have a wonderful day, goodbye!"
            }
            return concluding_messages.get(self.personality, "Thank you, bye!")

        current_turn = turns[self.turn_index]

        # In mock mode, we pick the dialogue based on turn index.
        # We can also check if the agent mentioned keywords to adapt slightly.
        message = current_turn.get(self.personality, current_turn.get("Polite"))
        self.conversation_history.append({"role": "customer", "content": message})
        return message

    def _generate_llm_response(self, api_key: str, provider: str = "openai") -> str:
        # Construct LLM prompt
        history_str = ""
        for turn in self.conversation_history:
            role_name = "Agent (Coaching console user)" if turn["role"] == "agent" else "Customer"
            history_str += f"{role_name}: {turn['content']}\n"

        system_instruction = (
            f"You are simulating a customer in a support chat scenario. Do not break character. Do not output anything other than the customer's response message.\n"
            f"Scenario: {self.scenario} - {MOCK_SIMULATOR_SCENARIOS[self.scenario]['description']}\n"
            f"Your Customer Personality: {self.personality}\n"
            f"Guidelines for your personality:\n"
            f"- If Angry: Demanding, uses exclamation marks, complains about quality, expresses frustration.\n"
            f"- If Confused: Needs simple explanations, asks clarifying questions, feels overwhelmed.\n"
            f"- If Impatient: Very short sentences, requests immediate action, mentions time limits.\n"
            f"- If Polite: Uses 'please', 'thank you', is understanding and cooperative.\n\n"
            f"Roleplay rules:\n"
            f"1. Generate only the NEXT message from the customer.\n"
            f"2. Keep it conversational, realistic, and short (1-3 sentences).\n"
            f"3. React naturally to what the Agent said last. If they asked a question, answer it. If they resolved the issue, be satisfied or ask final questions.\n"
            f"4. Do not prefix with 'Customer:' or 'Message:'."
        )

        try:
            from openai import OpenAI
            if provider == "groq":
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            elif provider == "gemini":
                # Gemini exposes an OpenAI-compatible endpoint; gemini-2.0-flash is on the free tier
                client = OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
                model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            else:
                client = OpenAI(api_key=api_key)
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Chat History:\n{history_str}\nNext Customer Message:"}
                ],
                max_tokens=150,
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()

            # Clean up response if LLM prefixed it
            text = text.replace("Customer:", "").strip()
            self.conversation_history.append({"role": "customer", "content": text})
            return text
        except Exception as e:
            # If API calls fail, fallback to mock dialog
            print(f"Error calling LLM in simulator, falling back to mock: {e}")
            return self._generate_mock_response("")