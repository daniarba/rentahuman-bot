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
    get_performance_report,
    evolve_strategy
)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

applied_tasks = set()
seen_task_ids = set()
daily_applications = 0
pending_approvals = {}
pending_work_review = {}
active_tasks = {}
memory = load_memory()

API_HEADERS = {
    "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json"
}

async def fetch_open_bounties():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://rentahuman.ai/api/bounties",
                headers=API_HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and data.get('success'):
                        bounties = data.get('bounties', [])
                        print(f"API status: {resp.status} | Bounties found: {len(bounties)}")
                        return bounties
                    elif isinstance(data, list):
                        return data
                return []
        except Exception as e:
            print(f"Fetch error: {e}")
            return []

async def fetch_accepted_tasks():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://rentahuman.ai/api/bounties/assigned",
                headers=API_HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and data.get('success'):
                        return data.get('bounties', [])
                    elif isinstance(data, list):
                        return data
                return []
        except Exception as e:
            print(f"Accepted fetch error: {e}")
            return []

async def apply_to_bounty(bounty_id: str, cover_letter: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://rentahuman.ai/api/bounties/{bounty_id}/apply",
                headers=API_HEADERS,
                json={"message": cover_letter}
            ) as resp:
                return resp.status in [200, 201]
        except Exception as e:
            print(f"Apply error: {e}")
            return False

async def submit_work(bounty_id: str, result_text: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://rentahuman.ai/api/bounties/{bounty_id}/submit",
                headers=API_HEADERS,
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

            print(f"Tasks dhundh raha hoon...")
            min_price = memory['strategy']['min_price']
            preferred = memory['strategy']['preferred_categories']
            avoided = memory['strategy']['avoided_categories']

            bounties = await fetch_open_bounties()
            found_new = False

            for b in bounties:
                if not isinstance(b, dict):
                    continue

                task_id = b.get('id')

                # Sirf naye tasks
                if task_id in seen_task_ids:
                    continue
                seen_task_ids.add(task_id)

                if task_id in applied_tasks:
                    continue
                if b.get('status') != 'open':
                    continue
                if b.get('price', 0) < min_price:
                    continue

                # Remote only check
                location = b.get('location', {})
                if isinstance(location, dict):
                    if not location.get('isRemoteAllowed', False):
                        continue

                category = b.get('category', '').lower()
                if any(av in category for av in avoided):
                    continue

                take, reason, confidence = should_take_task(
                    b.get('title', ''),
                    b.get('description', ''),
                    b.get('price', 0)
                )

                if preferred and any(p in category for p in preferred):
                    confidence = min(10, confidence + 2)

                if not take or confidence < 6:
                    print(f"SKIPPED: {b.get('title')} -> {reason}")
                    applied_tasks.add(task_id)
                    continue

                found_new = True
                cover_letter = generate_cover_letter(
                    b.get('title', ''),
                    b.get('description', '')
                )

                embed = discord.Embed(
                    title=f"💼 {b.get('title', 'Task')[:100]}",
                    color=0x3498db
                )
                embed.add_field(name="💰 Price", value=f"${b.get('price', '?')}", inline=True)
                embed.add_field(name="📂 Category", value=b.get('category', 'N/A'), inline=True)
                embed.add_field(name="🧠 AI Score", value=f"{confidence}/10 — {reason}", inline=False)
                embed.add_field(name="📝 Task", value=str(b.get('description', ''))[:300] + "...", inline=False)
                embed.add_field(name="✉️ Cover Letter", value=cover_letter[:400], inline=False)
                embed.set_footer(text="✅ Apply karo  |  ❌ Skip karo")

                msg = await channel.send(embed=embed)
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")
                pending_approvals[msg.id] = {'task': b, 'cover_letter': cover_letter}
                await asyncio.sleep(random.randint(30, 90))

            if not found_new:
                print("Koi naya task nahi mila — next check 15 min mein")

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
                    record_won(memory, task)
                    await channel.send(
                        f"🎉 **Task Mila!**\n"
                        f"**{task.get('title')}** — ${task.get('price')}\n"
                        f"Win Rate: {memory['stats']['win_rate']}%\n"
                        f"⏳ Kaam shuru kar raha hoon..."
                    )
                    asyncio.create_task(do_task_work(task, channel))
        except Exception as e:
            print(f"Accepted check error: {e}")
        await asyncio.sleep(10 * 60)

async def daily_evolution():
    global memory
    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    while not client.is_closed():
        now = datetime.now()
        if now.hour == 0 and now.minute < 15:
            memory = evolve_strategy(memory)
            report = get_performance_report(memory)
            await channel.send(f"🌙 **Raat Ki Report:**\n{report}")
        await asyncio.sleep(15 * 60)

async def do_task_work(task: dict, channel):
    global memory
    bounty_id = task.get('id')
    title = task.get('title', '')
    description = task.get('description', '')

    await channel.send(f"🤖 Kaam kar raha hoon: **{title[:80]}**\nThoda wait karo...")
    await asyncio.sleep(random.randint(60, 180))

    try:
        result = do_research_task(
            f"Task Title: {title}\n\nTask Description: {description}"
        )
        embed = discord.Embed(
            title="📋 Kaam Taiyar — Review Karo!",
            description=f"**Task:** {title[:100]}",
            color=0xf39c12
        )
        preview = result[:800] + "\n...(poora upload mein jayega)" if len(result) > 800 else result
        embed.add_field(name="📄 Preview", value=preview, inline=False)
        embed.add_field(name="💰 Price", value=f"${task.get('price', '?')}", inline=True)
        embed.set_footer(text="✅ Upload | ❌ Dobara karo | ✏️ Edit karke upload")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await msg.add_reaction("✏️")

        pending_work_review[msg.id] = {
            'task': task, 'result': result, 'bounty_id': bounty_id
        }
    except Exception as e:
        await channel.send(f"❌ Error: {str(e)}")

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
            f"🤖 **RentAHuman Bot Online!**\n"
            f"🏆 Level: **{level.upper()}**\n"
            f"✅ Tasks Done: {completed}\n"
            f"💰 Total Earned: ${earned}\n\n"
            f"**Commands:** `!status` | `!report` | `!help`"
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
                    f"**{task.get('title')}** — ${task.get('price')}\n"
                    f"Aaj: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}\n"
                    f"_Client ke reply ka wait karo..._"
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
                evolve_strategy(memory)
                await channel.send(
                    f"🎊 **Submit Ho Gaya!**\n"
                    f"**{task.get('title')}** — ${task.get('price')}\n"
                    f"💰 Total Earned: ${memory['stats']['total_earned']}\n"
                    f"_Payment ka wait karo!_\n\n"
                    f"_Rating aane pe: `!rating {bounty_id} 5 feedback`_"
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

    if message.content.startswith("!reply "):
        client_msg = message.content.replace("!reply ", "", 1)
        reply = reply_to_client_message(client_msg)
        await message.channel.send(f"💬 **Client Ko Bhejo:**\n```\n{reply}\n```")

    elif message.content.startswith("!rating "):
        parts = message.content.split(" ", 3)
        if len(parts) >= 3:
            try:
                bounty_id = parts[1]
                rating = int(parts[2])
                feedback = parts[3] if len(parts) > 3 else ""
                task = {'id': bounty_id, 'title': 'Task', 'price': 0}
                record_completed(memory, task, rating, feedback)
                evolve_strategy(memory)
                await message.channel.send(
                    f"⭐ Rating saved: {rating}/5\n"
                    f"Avg: {memory['stats']['avg_client_rating']}/5\n"
                    f"Bot learning! 🧠"
                )
            except:
                await message.channel.send("Format: `!rating <id> <1-5> <feedback>`")

    elif message.content.startswith("!submit "):
        parts = message.content.split(" ", 2)
        if len(parts) >= 3:
            success = await submit_work(parts[1], parts[2])
            await message.channel.send(
                "🎊 Submit ho gaya! 💰" if success else "❌ Submit fail"
            )

    elif message.content.lower() == "!status":
        await message.channel.send(
            f"📊 **Status:**\n"
            f"✅ Aaj apply: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}\n"
            f"🔨 Active tasks: {len(active_tasks)}\n"
            f"⏳ Apply pending: {len(pending_approvals)}\n"
            f"📋 Review pending: {len(pending_work_review)}\n"
            f"👁️ Dekhe tasks: {len(seen_task_ids)}"
        )

    elif message.content.lower() == "!report":
        await message.channel.send(get_performance_report(memory))

    elif message.content.lower() == "!help":
        await message.channel.send(
            "🤖 **Commands:**\n"
            "`!status` — Aaj ka status\n"
            "`!report` — Poori performance\n"
            "`!reply <msg>` — Client reply generate\n"
            "`!rating <id> <1-5> <feedback>` — Rating save\n"
            "`!submit <id> <text>` — Manual submit\n\n"
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
