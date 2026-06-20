import os
import requests
import discord
from discord.ext import tasks
from google import genai

# Environment Variables (Railway safe)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
RENTAHUMAN_API_KEY = os.environ.get("RENTAHUMAN_API_KEY")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")
BASE_URL = "https://rentahuman.ai/api"
CHECK_INTERVAL_MINUTES = 10

# Google GenAI Setup (Latest SDK)
client = None
if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY environment variable missing!")
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

HUMAN_PROFILE = """
My name is Arba. I am a freelancer from malaysia.
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
    "design logo", "graphic design", "audio", "podcast",
    "bank account", "sell me your bank", "remittance", "dispatch worker"
]


def ask_gemini(prompt: str) -> str:
    """Gemini se jawab lo using new SDK"""
    if client is None:
        return ""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
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
Arba CANNOT do: physical tasks, delivery, design, video, audio.

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
            except Exception:
                confidence = 5

    return decision == "yes", reason, confidence


def fetch_bounties():
    """RentAHuman se direct remote bounties check karne ka function"""
    print("Tasks dhundh raha hoon...")
    if not RENTAHUMAN_API_KEY:
        print("❌ Error: RENTAHUMAN_API_KEY environment variable missing!")
        return []

    headers = {"Authorization": f"Bearer {RENTAHUMAN_API_KEY}"}
    try:
        response = requests.get(f"{BASE_URL}/bounties?remote=true", headers=headers, timeout=20)
        if response.status_code == 200:
            bounties = response.json().get("bounties", [])
            print(f"API status: 200 | Bounties found: {len(bounties)}")
            return bounties
        else:
            print(f"API Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Network error: {e}")
        return []


# ---------------- Discord Bot Setup ----------------

intents = discord.Intents.default()
bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Discord bot connected as {bot.user} (auto worker)")
    if DISCORD_CHANNEL_ID:
        channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
        if channel:
            await channel.send("✅ **Bot is now active** and scanning RentAHuman bounties every "
                                f"{CHECK_INTERVAL_MINUTES} minutes.")
    if not check_bounties_loop.is_running():
        check_bounties_loop.start()


@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_bounties_loop():
    channel = None
    if DISCORD_CHANNEL_ID:
        channel = bot.get_channel(int(DISCORD_CHANNEL_ID))

    bounties = fetch_bounties()

    if not bounties:
        if channel:
            await channel.send("⚠️ No bounties found this cycle (or API error). Will check again soon.")
        return

    for bounty in bounties[:5]:
        title = bounty.get("title", "No Title")
        desc = bounty.get("description", "No Description")
        price = float(bounty.get("price", 0))

        take, reason, conf = should_take_task(title, desc, price)

        if take:
            msg = (f"✅ **ACCEPTED**: {title}\n"
                   f"💰 Price: ${price}\n"
                   f"📊 Confidence: {conf}/10\n"
                   f"📝 Reason: {reason}")
            print(f"Apply Status 200: {title} (Confidence: {conf}/10)")
        else:
            msg = f"⏭️ **SKIPPED**: {title}\n📝 Reason: {reason}"
            print(f"Skip: {title} -> {reason}")

        if channel:
            await channel.send(msg)


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN environment variable missing! Bot cannot start.")
    else:
        bot.run(DISCORD_BOT_TOKEN)
