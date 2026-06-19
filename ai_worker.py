import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def generate_cover_letter(task_title: str, task_description: str) -> str:
    prompt = f"""You are a professional freelancer applying for a task.
Write a SHORT, natural, human-like application message (max 100 words).

Task Title: {task_title}
Task Description: {task_description}

Rules:
- Sound completely human, NOT like AI
- No robotic phrases
- Be confident and specific
- Simple English only
- No bullet points

Write ONLY the message, nothing else."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def do_research_task(task_description: str) -> str:
    prompt = f"""You are a professional freelancer. Complete this task thoroughly and accurately.

{task_description}

Rules:
- Be detailed and accurate
- Use clear formatting
- Sound like a human expert
- Provide complete, useful information
- No AI-sounding phrases"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
