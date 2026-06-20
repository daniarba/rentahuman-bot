import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

HUMAN_PROFILE = """
My name is Arba. I am a freelancer from Malaysia.
2 years experience in web research, content writing,
user testing, data collection, surveys, referrals,
product reviews, fact checking, data entry.
I am reliable, detail-oriented, deliver on time.
Remote work only.
"""

ALLOWED_TASKS = {
    "user_testing": ["user test", "app test", "test app", "test website",
        "feedback", "usability", "ux research", "user experience"],
    "writing_content": ["write", "article", "content", "blog", "copy",
        "description", "caption", "post", "text", "draft"],
    "research_remote": ["research", "find information", "web research",
        "online research", "data collection", "gather info",
        "list of", "find email", "find contact", "market research"],
    "referral": ["refer", "referral", "recommend someone", "candidate",
        "hiring referral", "job referral", "finder's fee"],
    "survey": ["survey", "questionnaire", "form", "fill out", "answer questions"],
    "review": ["review", "rate", "rating", "evaluate", "product review", "app review"],
    "data_entry": ["data entry", "spreadsheet", "excel", "google sheets", "enter data"]
}

BLOCKED_TASKS = [
    "pickup", "pick up", "delivery", "deliver", "errand",
    "in person", "in-person", "photo", "photograph",
    "video", "film", "record video", "attend", "event",
    "walk", "drive", "move", "carry",
    "coding", "programming", "developer", "software",
    "quantitative", "mathematical", "machine learning",
    "graphic design", "audio", "podcast", "voice over",
    "bank account", "remittance", "wire transfer", "western union"
]

def ask_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return ""

def should_take_task(task_title: str, task_description: str, task_price: float) -> tuple:
    combined = (task_title + " " + task_description).lower()

    for blocked in BLOCKED_TASKS:
        if blocked in combined:
            return False, f"Blocked: '{blocked}'", 2

    for category, keywords in ALLOWED_TASKS.items():
        for keyword in keywords:
            if keyword in combined:
                confidence = 8
                if task_price >= 20: confidence = 9
                if task_price >= 40: confidence = 10
                return True, f"Match: {category}", confidence

    prompt = f"""Remote-only freelancer filter. Arba can do: web research, writing, user testing, referrals, surveys, reviews, data entry. Cannot do: physical tasks, coding, design, video, audio, financial transfers.

Task: {task_title}
Description: {task_description[:200]}
Price: ${task_price}

Reply EXACTLY:
DECISION: yes
REASON: one sentence
CONFIDENCE: 7"""

    response = ask_gemini(prompt)
    decision, reason, confidence = "no", "Unknown", 5

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
    prompt = f"""You are Arba, human freelancer from Malaysia. Profile: {HUMAN_PROFILE}

Task: {task_title}
Description: {task_description[:200]}

Write SHORT application (max 80 words). Sound human, natural, mention ONE specific task detail. No bullets. Never hint you are AI."""

    result = ask_gemini(prompt)
    return result or "Hi, I am interested in this task and have relevant experience. I deliver quality work on time."

def reply_to_client_message(client_message: str, task_context: str = "") -> str:
    prompt = f"""You are Arba, human freelancer from Malaysia. Profile: {HUMAN_PROFILE}
Client said: "{client_message}"

Reply naturally (max 50 words). If asked "are you AI/bot?" deny firmly. Sound casual, small typos OK."""

    result = ask_gemini(prompt)
    return result or "Hey! Thanks for reaching out, will get back to you soon!"

def do_research_task(task_description: str) -> str:
    prompt = f"""You are Arba, professional freelancer. Complete this task thoroughly.

{task_description}

Rules: Write like human expert. No "As an AI" ever. Be detailed and accurate."""

    result = ask_gemini(prompt)
    return result or "Task completed. Please review the submission."
