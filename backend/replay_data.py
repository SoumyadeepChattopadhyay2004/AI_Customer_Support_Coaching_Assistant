from typing import List, Dict, Any

REPLAY_TRANSCRIPTS = {
    "replay_double_charge": {
        "id": "replay_double_charge",
        "title": "Double Charge Billing Issue",
        "scenario": "Billing Dispute",
        "personality": "Angry",
        "turns": [
            {
                "turn_index": 0,
                "sender": "customer",
                "text": "Hi, I just looked at my credit card statement and your company charged me twice for my subscription this month! This is ridiculous, I need this refunded immediately."
            },
            {
                "turn_index": 1,
                "sender": "agent",
                "text": "Hello, thank you for reaching out. I'm sorry to hear that you were charged twice. Can I please get your email address and order details to check this?"
            },
            {
                "turn_index": 2,
                "sender": "customer",
                "text": "My email is jenny.smith@example.com. The charges were both on July 10th for $29.99 each. Please hurry, I don't want to wait."
            },
            {
                "turn_index": 3,
                "sender": "agent",
                "text": "Thank you, Jenny. I see the account under your email. There is indeed one processed transaction and one pending authorization charge. I will initiate a refund for the second duplicate charge right away."
            },
            {
                "turn_index": 4,
                "sender": "customer",
                "text": "Thank you. When will I get my money back? This is a lot of money for me right now."
            },
            {
                "turn_index": 5,
                "sender": "agent",
                "text": "I have processed the refund. You should see the funds back in your account in 3 to 5 business days, depending on your bank. I apologize again for the inconvenience."
            },
            {
                "turn_index": 6,
                "sender": "customer",
                "text": "Okay, that sounds fair. Thanks for resolving this so quickly. I appreciate it."
            }
        ]
    },
    "replay_wifi_issues": {
        "id": "replay_wifi_issues",
        "title": "Slow Internet & Router Troubleshooting",
        "scenario": "Technical Issue",
        "personality": "Confused",
        "turns": [
            {
                "turn_index": 0,
                "sender": "customer",
                "text": "Hello, my router has a red light on it and my internet is barely working. I have a big work meeting in 15 minutes, please help me!"
            },
            {
                "turn_index": 1,
                "sender": "agent",
                "text": "Hi there! I can help you with that. A red light means the router is having trouble connecting to the network. Let's start by unplugging it for 30 seconds."
            },
            {
                "turn_index": 2,
                "sender": "customer",
                "text": "Okay, I've unplugged it. I'm waiting. Let's hope this works..."
            },
            {
                "turn_index": 3,
                "sender": "agent",
                "text": "Great! Now plug it back in. It will take about 2 minutes to reboot. Tell me what color the LED light is once it starts back up."
            },
            {
                "turn_index": 4,
                "sender": "customer",
                "text": "It's still flashing red. This is so stressful, I'm going to miss my meeting. What else can we do?"
            },
            {
                "turn_index": 5,
                "sender": "agent",
                "text": "Since it's still red, we need to perform a factory reset. Press and hold the small Reset button on the back of the router with a pin for 15 seconds."
            },
            {
                "turn_index": 6,
                "sender": "customer",
                "text": "Okay, I did that. Oh wait, now it's blinking white! And the light just turned green! My internet is back!"
            },
            {
                "turn_index": 7,
                "sender": "agent",
                "text": "Awesome! I'm glad it's back up. Good luck with your meeting!"
            }
        ]
    },
    "replay_cancellation": {
        "id": "replay_cancellation",
        "title": "Account Cancellation Save Attempt",
        "scenario": "Subscription Save",
        "personality": "Polite but persistent",
        "turns": [
            {
                "turn_index": 0,
                "sender": "customer",
                "text": "Hi, I would like to cancel my premium subscription. It is too expensive for me right now and I am not using it enough."
            },
            {
                "turn_index": 1,
                "sender": "agent",
                "text": "Hi! I understand that cost is an issue. Before we cancel, would you be interested in keeping your account if I could offer you 1 month free or downgrade you to our Starter package for just $9 a month?"
            },
            {
                "turn_index": 2,
                "sender": "customer",
                "text": "That's a nice offer, but I really just want to cancel. I'm moving onto a different project and won't need this tool at all."
            },
            {
                "turn_index": 3,
                "sender": "agent",
                "text": "I understand. I'll go ahead and cancel the subscription for you immediately. You won't be charged again, and you'll still have premium access until the end of your billing cycle on July 25th."
            },
            {
                "turn_index": 4,
                "sender": "customer",
                "text": "Perfect, thank you so much for make this easy. Have a great day!"
            }
        ]
    }
}
