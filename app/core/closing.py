import random
from app.config.config import get_settings

settings = get_settings()

FOLLOWUP_LINES_FIRST = [
    "Is there anything else I can help you with?",
    "Anything else you need from my side?",
    "Would you like help with anything else today?",
]

FOLLOWUP_LINES_SECOND = [
    "Sorry i am not able hear you, anything else I can help you with?",
    "Checking again, Do you need more help?",
    "I am not able to hear you, Can i help you with anything else?",
]

CLOSING_LINES = [
    "Thanks for calling, have a great day!",
    "Glad I could help. Have a wonderful day!",
    f"Thank you for calling {settings.lab_name}. Goodbye!",
]

def pick(lines: list[str]) -> str:
    return random.choice(lines)