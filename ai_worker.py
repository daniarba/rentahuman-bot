from google import genai
import os
from config import GEMINI_API_KEY

# Gemini setup
client_ai = genai.Client(api_key=GEMINI_API_KEY)
  # Free tier

HUMAN_PROFILE = """
My name is Arba. I am a freelancer from Pakistan.
I have 2 years experience in:
- Web research and data collection
- Writing articles and content
- User testing and app feedback
- Fact checking and verification
- Survey completion
- Referral and hiring tasks
- Product reviews and feedback
I am detail-oriented, reliable, and deliver on time.
I prefer remote work only.
"""

ALLOWED_TASKS = {
    "user_testing": ["user test", "app test", "test app", "test website",
        "feedback", "usability", "ux research", "user experience",
        "record feedback", "test and feedback"],
    "writing_content": ["write", "article", "content", "blog", "copy",
        "description", "caption", "post", "text", "draft"],
    "research_remote": ["research", "find information", "web research",
        "online research", "data collection", "gather info", "compile",
        "list of", "find email", "find contact", "market research"],
    "referral": ["refer", "referral", "recommend someone", "candidate",
        "hiring referral", "job referral", "finder's fee"],
    "survey": ["survey", "questionnaire", "form", "fill out",
        "complete survey", "answer questions"],
    "review": ["review", "rate", "rating", "evaluate",
        "product review", "app review", "leave review"],
    "data_entry": ["data entry", "spreadsheet", "excel", "google sheets",
        "enter data", "fill data", "organize data"]
}

BLOCKED_TASKS = [
    "pickup", "pick up", "delivery", "deliver", "errand",
    "in person", "in-person", "local", "photo", "photograph",
    "video", "film", "record video", "attend", "event",
    "walk", "drive", "move", "carry", "install physically",
    "coding", "programming", "developer", "software",
    "quantitative", "mathematical", "machine learning",
    "design logo", "graphic design", "audio", "podcast"
]

def ask_gemini(prompt: str, max_words: int = 200) -> str:
    """Gemini se jawab lo"""
    try:
        response = client_ai.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return ""

def should_take_task(task_title: str, task_description: str, task_price: float) -> tuple:
    title_lower = task_title.lower()
    desc_lower = task_description.lower()
    combined = title_lower + " " + desc_lower

    for blocked in BLOCKED_TASKS:
        if blocked in combined:
            return False, f"Blocked: '{blocked}'", 2

    for category, keywords in ALLOWED_TASKS.items():
        for keyword in keywords:
            if keyword in combined:
                confidence = 8
                if task_price >= 20:
                    confidence = 9
                if task_price >= 40:
                    confidence = 10
                return True, f"Match: {category}", confidence

    prompt = f"""You are a task filter for a REMOTE-ONLY freelancer named Arba from Pakistan.

Arba can ONLY do: web research, content writing, user testing, referrals, surveys, reviews, data entry.
Arba CANNOT do: physical tasks, delivery, coding, design, video, audio.

Task: {task_title}
Description: {task_description[:300]}
Price: ${task_price}

Reply EXACTLY in this format:
DECISION: yes
REASON: one sentence
CONFIDENCE: 7"""

    response = ask_gemini(prompt)
    decision = "no"
    reason = "Unknown"
    confidence = 5

    for line in response.split('\n'):
        line = line.strip()
        if line.startswith("DECISION:"):
            decision = line.replace("DECISION:", "").strip().lower()
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
        elif line.startswith("CONFIDENCE:"):
            try:
                confidence = int(line.replace("CONFIDENCE:", "").strip())
            except:
                confidence = 5

    return decision == "yes", reason, confidence

def generate_cover_letter(task_title: str, task_description: str) -> str:
    prompt = f"""You are Arba, a human freelancer from Pakistan.

Profile: {HUMAN_PROFILE}

Task: {task_title}
Description: {task_description[:300]}

Write a SHORT application message (max 80 words).
Rules:
- You are HUMAN, never hint you are AI
- Sound natural and conversational
- Small grammar mistakes OK
- Mention ONE specific detail from the task
- No bullet points

Write ONLY the message."""

    result = ask_gemini(prompt)
    return result if result else "Hi, I am interested in this task and have relevant experience. I can deliver quality work on time. Please consider my application."

def reply_to_client_message(client_message: str, task_context: str = "") -> str:
    prompt = f"""You are Arba, a human freelancer from Pakistan.

Profile: {HUMAN_PROFILE}
Task Context: {task_context}
Client said: "{client_message}"

Reply naturally as a human freelancer.
Rules:
- If asked "are you AI/bot?" — deny firmly: "No haha I'm a real person!"
- Sound casual and natural
- Max 50 words
- Small typos OK

Write ONLY the reply."""

    result = ask_gemini(prompt)
    return result if result else "Hey thanks for reaching out! I'm working on it and will update you soon."

def do_research_task(task_description: str) -> str:
    prompt = f"""You are Arba, a professional freelancer completing a task.

{task_description}

Complete this task thoroughly.
Rules:
- Write like a human expert
- No "As an AI" phrases ever
- Be detailed and accurate
- Deliver exactly what was asked"""

    result = ask_gemini(prompt)
    return result if result else "Task completed. Please review the submission."
