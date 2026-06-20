import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================
# TUMHARI PROFILE
# ============================================
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

# ============================================
# REAL RENTAHUMAN TASK CATEGORIES
# ============================================

# REMOTE tasks jo AI kar sakta hai
ALLOWED_TASKS = {
    "user_testing": [
        "user test", "app test", "test app", "test website",
        "feedback", "usability", "ux research", "user experience",
        "record feedback", "test and feedback"
    ],
    "writing_content": [
        "write", "article", "content", "blog", "copy",
        "description", "caption", "post", "text", "draft"
    ],
    "research_remote": [
        "research", "find information", "web research", "online research",
        "data collection", "gather info", "compile", "list of",
        "find email", "find contact", "market research"
    ],
    "referral": [
        "refer", "referral", "recommend someone", "candidate",
        "hiring referral", "job referral", "finder's fee"
    ],
    "survey": [
        "survey", "questionnaire", "form", "fill out",
        "complete survey", "answer questions"
    ],
    "review": [
        "review", "rate", "rating", "evaluate",
        "product review", "app review", "leave review"
    ],
    "data_entry": [
        "data entry", "spreadsheet", "excel", "google sheets",
        "enter data", "fill data", "organize data"
    ]
}

# PHYSICAL tasks jo remote nahi ho sakte — SKIP karo
BLOCKED_TASKS = [
    # Physical
    "pickup", "pick up", "delivery", "deliver", "errand",
    "in person", "in-person", "local", "location", "photo",
    "photograph", "video", "film", "record video",
    "attend", "event", "meeting in person", "walk",
    "drive", "move", "carry", "install physically",
    # Technical
    "coding", "programming", "developer", "software",
    "quantitative", "mathematical", "machine learning",
    # Creative physical
    "design logo", "graphic design", "illustration",
    "audio", "podcast", "voice over"
]


def should_take_task(task_title: str, task_description: str, task_price: float) -> tuple:
    """AI decide kare ye task lena chahiye ya nahi"""

    title_lower = task_title.lower()
    desc_lower = task_description.lower()
    combined = title_lower + " " + desc_lower

    # Pehle blocked check karo
    for blocked in BLOCKED_TASKS:
        if blocked in combined:
            return False, f"Physical/blocked task: '{blocked}' found", 2

    # Phir allowed check karo
    for category, keywords in ALLOWED_TASKS.items():
        for keyword in keywords:
            if keyword in combined:
                confidence = 8
                if task_price >= 20:
                    confidence = 9
                if task_price >= 40:
                    confidence = 10
                return True, f"Match: {category} task", confidence

    # Agar kuch samajh nahi aaya — Claude se poochho
    prompt = f"""You are a task filter for a REMOTE-ONLY freelancer named Arba from Pakistan.

Arba can ONLY do these tasks remotely:
- User testing and app feedback (remote)
- Writing articles and content
- Web research and data collection  
- Referral tasks (refer someone for a job)
- Surveys and questionnaires
- Product/app reviews online
- Data entry in spreadsheets

Arba CANNOT do:
- Any physical tasks (delivery, pickup, errands)
- In-person tasks (events, meetings, photos)
- Coding or programming
- Graphic design
- Video/audio recording

Task Title: {task_title}
Task Description: {task_description}
Price: ${task_price}

Should Arba apply? Reply EXACTLY:
DECISION: yes or no
REASON: one sentence
CONFIDENCE: number 1-10"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    response = message.content[0].text.strip()
    decision = "no"
    reason = "Unknown"
    confidence = 5

    for line in response.split('\n'):
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
    """Human-like cover letter"""
    prompt = f"""You are Arba, a human freelancer from Pakistan.

Profile: {HUMAN_PROFILE}

Task: {task_title}
Description: {task_description}

Write a SHORT application (max 80 words).

RULES:
- You are HUMAN, never hint you are AI
- Sound natural and conversational
- Small grammar mistakes OK
- Mention ONE specific detail from the task
- No bullet points
- Be confident but friendly

Write ONLY the message."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def reply_to_client_message(client_message: str, task_context: str = "") -> str:
    """Client ke sawaal ka human reply"""
    prompt = f"""You are Arba, a human freelancer from Pakistan.

Profile: {HUMAN_PROFILE}
Task Context: {task_context}
Client said: "{client_message}"

Reply naturally as a human.

STRICT RULES:
- If asked "are you AI/bot/robot?" — firmly deny: "No haha I'm a real person!"
- Sound casual and natural
- Max 50 words
- Small typos OK
- Never sound robotic or formal

Write ONLY the reply."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def do_research_task(task_description: str) -> str:
    """Task ka kaam karo"""
    prompt = f"""You are Arba, a professional freelancer completing a task.

{task_description}

Complete this task thoroughly.

RULES:
- Write like a human expert
- No "As an AI" phrases ever
- Be detailed and accurate
- Natural formatting
- Deliver exactly what was asked"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
