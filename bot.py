import discord
import asyncio
import aiohttp
import random
from datetime import datetime
from config import (
    RENTAHUMAN_API_KEY,
    DISCORD_BOT_TOKEN,
    DISCORD_CHANNEL_ID,
    CHECK_INTERVAL_MINUTES,
    MAX_APPLICATIONS_PER_DAY
)
from ai_worker import (
    generate_cover_letter,
    do_research_task,
    should_take_task,
    reply_to_client_message
)
from memory import (
    load_memory,
    record_applied,
    record_won,
    record_completed,
    record_rejected,
    get_performance_report,
    evolve_strategy
)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# State
applied_tasks = set()
daily_applications = 0
pending_approvals = {}
pending_work_review = {}
active_tasks = {}

# Memory load karo
memory = load_memory()

async def fetch_open_bounties():
    headers = {
        "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://rentahuman.ai/api/bounties",
                headers=headers,
                params={"status": "open"}
            ) as resp:
                print(f"API status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return (data.get('bounties') or data.get('data') or
                                data.get('results') or data.get('items') or [])
                return []
        except Exception as e:
            print(f"Fetch error: {e}")
            return []

async def fetch_accepted_tasks():
    headers = {
        "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://rentahuman.ai/api/bounties/assigned",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return (data.get('bounties') or data.get('data') or [])
                return []
        except Exception as e:
            print(f"Accepted fetch error: {e}")
            return []

async def apply_to_bounty(bounty_id: str, cover_letter: str):
    headers = {
        "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://rentahuman.ai/api/bounties/{bounty_id}/apply",
                headers=headers,
                json={"message": cover_letter}
            ) as resp:
                return resp.status in [200, 201]
        except Exception as e:
            print(f"Apply error: {e}")
            return False

async def submit_work(bounty_id: str, result_text: str):
    headers = {
        "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://rentahuman.ai/api/bounties/{bounty_id}/submit",
                headers=headers,
                json={"submission": result_text}
            ) as resp:
                return resp.status in [200, 201]
        except Exception as e:
            print(f"Submit error: {e}")
            return False

async def hunt_tasks():
    global daily_applications, memory
    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    while not client.is_closed():
        try:
            if daily_applications >= MAX_APPLICATIONS_PER_DAY:
                await channel.send("⏸️ Daily limit ho gaya! Kal phir shuru karunga.")
                await asyncio.sleep(3600)
                daily_applications = 0
                continue

            print(f"[{datetime.now().strftime('%H:%M')}] Tasks dhundh raha hoon...")

            # Memory se min price lo (level ke hisab se)
            min_price = memory['strategy']['min_price']
            preferred = memory['strategy']['preferred_categories']
            avoided = memory['strategy']['avoided_categories']

            bounties = await fetch_open_bounties()
            print(f"Total bounties: {len(bounties)}")

            for b in bounties:
                if not isinstance(b, dict):
                    continue
                if b.get('id') in applied_tasks:
                    continue
                if b.get('status') != 'open':
                    continue
                if b.get('price', 0) < min_price:
                    continue

                # Avoided categories skip karo
                category = b.get('category', '').lower()
                if any(av in category for av in avoided):
                    print(f"Avoided category skip: {b.get('title')}")
                    continue

                # AI se poochho
                take, reason, confidence = should_take_task(
                    b.get('title', ''),
                    b.get('description', ''),
                    b.get('price', 0)
                )

                # Preferred categories ko boost do
                if preferred and any(p in category for p in preferred):
                    confidence = min(10, confidence + 2)

                if not take or confidence < 6:
                    print(f"Skip: {b.get('title')} — {reason} ({confidence}/10)")
                    applied_tasks.add(b.get('id'))
                    continue

                cover_letter = generate_cover_letter(
                    b.get('title', ''),
                    b.get('description', '')
                )

                embed = discord.Embed(
                    title=f"💼 {b.get('title', 'Task')}",
                    color=0x3498db
                )
                embed.add_field(name="💰 Price", value=f"${b.get('price', '?')}", inline=True)
                embed.add_field(name="⏰ Deadline", value=b.get('deadline', 'N/A'), inline=True)
                embed.add_field(name="🧠 AI Score", value=f"{confidence}/10 — {reason}", inline=False)
                embed.add_field(name="📝 Task", value=str(b.get('description', ''))[:300] + "...", inline=False)
                embed.add_field(name="✉️ Cover Letter", value=cover_letter[:400], inline=False)
                embed.set_footer(text="✅ Apply | ❌ Skip")

                msg = await channel.send(embed=embed)
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")
                pending_approvals[msg.id] = {'task': b, 'cover_letter': cover_letter}
                await asyncio.sleep(random.randint(30, 90))

        except Exception as e:
            print(f"Hunt error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

async def check_accepted_tasks():
    global memory
    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    while not client.is_closed():
        try:
            accepted = await fetch_accepted_tasks()
            for task in accepted:
                if not isinstance(task, dict):
                    continue
                bounty_id = task.get('id')
                if bounty_id and bounty_id not in active_tasks:
                    active_tasks[bounty_id] = task

                    # Memory mein record karo
                    record_won(memory, task)

                    await channel.send(
                        f"🎉 **Task Mila!**\n"
                        f"**{task.get('title')}** — ${task.get('price')}\n"
                        f"📈 Win Rate: {memory['stats']['win_rate']}%\n"
                        f"⏳ Kaam shuru kar raha hoon..."
                    )
                    asyncio.create_task(do_task_work(task, channel))

        except Exception as e:
            print(f"Accepted check error: {e}")

        await asyncio.sleep(10 * 60)

async def daily_evolution():
    """Har raat bot khud ko improve kare"""
    global memory
    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    while not client.is_closed():
        # Raat 12 baje evolve karo
        now = datetime.now()
        if now.hour == 0 and now.minute < 15:
            print("Bot evolving strategy...")
            memory = evolve_strategy(memory)
            report = get_performance_report(memory)
            await channel.send(
                f"🌙 **Raat Ki Report — Bot Improve Ho Gaya!**\n{report}"
            )
        await asyncio.sleep(15 * 60)

async def do_task_work(task: dict, channel):
    global memory
    bounty_id = task.get('id')
    title = task.get('title', '')
    description = task.get('description', '')

    await channel.send(f"🤖 Kaam kar raha hoon: **{title}**\nThoda wait karo...")
    await asyncio.sleep(random.randint(60, 180))

    try:
        result = do_research_task(
            f"Task Title: {title}\n\nTask Description: {description}"
        )

        embed = discord.Embed(
            title="📋 Kaam Taiyar — Review Karo!",
            description=f"**Task:** {title}",
            color=0xf39c12
        )
        preview = result[:800] + "\n...(poora upload mein jayega)" if len(result) > 800 else result
        embed.add_field(name="📄 Preview", value=preview, inline=False)
        embed.add_field(name="💰 Price", value=f"${task.get('price', '?')}", inline=True)
        embed.set_footer(text="✅ Upload | ❌ Dobara | ✏️ Edit")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await msg.add_reaction("✏️")

        pending_work_review[msg.id] = {
            'task': task, 'result': result, 'bounty_id': bounty_id
        }

    except Exception as e:
        await channel.send(f"❌ Error: {title} — `{str(e)}`")

@client.event
async def on_ready():
    global memory
    print(f"✅ Bot ready! {client.user}")
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    level = memory['strategy']['current_level']
    earned = memory['stats']['total_earned']
    completed = memory['stats']['total_completed']

    if channel:
        await channel.send(
            f"🤖 **RentAHuman Bot Online!**\n\n"
            f"🏆 Level: **{level.upper()}**\n"
            f"✅ Tasks Done: {completed}\n"
            f"💰 Total Earned: ${earned}\n\n"
            f"🔍 Har 15 min tasks dhundhta hun\n"
            f"🧠 Har raat khud improve hota hun\n"
            f"💬 Client questions ka human reply deta hun\n\n"
            f"**Commands:** `!status` | `!report` | `!rating` | `!help`"
        )

@client.event
async def on_reaction_add(reaction, user):
    global daily_applications, memory
    if user.bot:
        return

    msg_id = reaction.message.id
    channel = reaction.message.channel
    emoji = str(reaction.emoji)

    if msg_id in pending_approvals:
        data = pending_approvals.pop(msg_id)
        task = data['task']
        cover_letter = data['cover_letter']

        if emoji == "✅":
            await channel.send(f"⏳ Apply kar raha hoon: **{task.get('title')}**...")
            await asyncio.sleep(random.randint(5, 15))
            success = await apply_to_bounty(task['id'], cover_letter)
            if success:
                applied_tasks.add(task['id'])
                daily_applications += 1
                record_applied(memory, task, cover_letter)
                await channel.send(
                    f"✅ **Apply Ho Gaya!**\n"
                    f"Task: **{task.get('title')}** — ${task.get('price')}\n"
                    f"Aaj: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}\n"
                    f"Win Rate: {memory['stats']['win_rate']}%"
                )
            else:
                await channel.send(f"❌ Apply fail — **{task.get('title')}**")

        elif emoji == "❌":
            applied_tasks.add(task['id'])
            await channel.send(f"⏭️ Skip: **{task.get('title')}**")

    elif msg_id in pending_work_review:
        data = pending_work_review.pop(msg_id)
        task = data['task']
        result = data['result']
        bounty_id = data['bounty_id']

        if emoji == "✅":
            await channel.send(f"📤 Upload kar raha hoon...")
            await asyncio.sleep(random.randint(3, 8))
            success = await submit_work(bounty_id, result)
            if success:
                active_tasks.pop(bounty_id, None)
                record_completed(memory, task)
                memory = evolve_strategy(memory)
                await channel.send(
                    f"🎊 **Submit Ho Gaya!**\n"
                    f"Task: **{task.get('title')}** — ${task.get('price')}\n"
                    f"Total Earned: ${memory['stats']['total_earned']}\n"
                    f"💰 Payment ka wait karo!\n\n"
                    f"_Rating aane pe `!rating {bounty_id} 5 Feedback yahan` likho_"
                )
            else:
                await channel.send(f"❌ Submit fail — manually check karo!")

        elif emoji == "❌":
            await channel.send(f"🔄 Dobara kar raha hoon...")
            asyncio.create_task(do_task_work(task, channel))

        elif emoji == "✏️":
            await channel.send(f"✏️ Edit karo phir: `!submit {bounty_id} <edited text>`")
            chunks = [result[i:i+1800] for i in range(0, len(result), 1800)]
            for chunk in chunks:
                await channel.send(f"```\n{chunk}\n```")
            pending_work_review[msg_id] = data

@client.event
async def on_message(message):
    global memory
    if message.author.bot:
        return

    # Client reply generate karo
    if message.content.startswith("!reply "):
        client_msg = message.content.replace("!reply ", "", 1)
        reply = reply_to_client_message(client_msg)
        await message.channel.send(f"💬 **Client Ko Bhejo:**\n```\n{reply}\n```")

    # Client rating save karo
    elif message.content.startswith("!rating "):
        parts = message.content.split(" ", 3)
        if len(parts) >= 3:
            bounty_id = parts[1]
            try:
                rating = int(parts[2])
                feedback = parts[3] if len(parts) > 3 else ""
                # Find task
                task = next(
                    (t for t in memory['tasks']['won'] if t.get('id') == bounty_id),
                    {'id': bounty_id, 'title': 'Unknown', 'price': 0}
                )
                record_completed(memory, task, rating, feedback)
                memory = evolve_strategy(memory)
                await message.channel.send(
                    f"⭐ Rating saved: {rating}/5\n"
                    f"Avg Rating: {memory['stats']['avg_client_rating']}/5\n"
                    f"Bot is learning from this! 🧠"
                )
            except:
                await message.channel.send("Format: `!rating <bounty_id> <1-5> <feedback>`")

    # Manual submit
    elif message.content.startswith("!submit "):
        parts = message.content.split(" ", 2)
        if len(parts) >= 3:
            bounty_id = parts[1]
            edited_text = parts[2]
            success = await submit_work(bounty_id, edited_text)
            if success:
                await message.channel.send(f"🎊 Submit ho gaya! 💰")
            else:
                await message.channel.send(f"❌ Submit fail")

    # Status
    elif message.content.lower() == "!status":
        await message.channel.send(
            f"📊 **Status:**\n"
            f"✅ Aaj apply: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}\n"
            f"🔨 Active: {len(active_tasks)}\n"
            f"⏳ Pending apply: {len(pending_approvals)}\n"
            f"📋 Pending review: {len(pending_work_review)}"
        )

    # Full report
    elif message.content.lower() == "!report":
        report = get_performance_report(memory)
        await message.channel.send(report)

    # Help
    elif message.content.lower() == "!help":
        await message.channel.send(
            "🤖 **Commands:**\n"
            "`!status` — Aaj ka status\n"
            "`!report` — Poori performance report\n"
            "`!reply <msg>` — Client ko human reply\n"
            "`!rating <id> <1-5> <feedback>` — Rating save karo\n"
            "`!submit <id> <text>` — Edited kaam submit\n\n"
            "**Reactions:**\n"
            "✅ Apply / Upload\n"
            "❌ Skip / Dobara\n"
            "✏️ Edit karke upload"
        )

async def main():
    async with client:
        asyncio.ensure_future(hunt_tasks())
        asyncio.ensure_future(check_accepted_tasks())
        asyncio.ensure_future(daily_evolution())
        await client.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
