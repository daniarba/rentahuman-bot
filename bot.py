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
    MIN_TASK_PRICE,
    MAX_APPLICATIONS_PER_DAY
)
from ai_worker import (
    generate_cover_letter,
    do_research_task,
    should_take_task,
    reply_to_client_message
)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

applied_tasks = set()
daily_applications = 0
pending_approvals = {}
pending_work_review = {}
active_tasks = {}

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
                print(f"Bounties API status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return (data.get('bounties') or
                                data.get('data') or
                                data.get('results') or
                                data.get('items') or [])
                    return []
                else:
                    text = await resp.text()
                    print(f"API Error {resp.status}: {text[:200]}")
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
                        return (data.get('bounties') or
                                data.get('data') or
                                data.get('results') or [])
                return []
        except Exception as e:
            print(f"Accepted tasks fetch error: {e}")
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
    global daily_applications
    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    while not client.is_closed():
        try:
            if daily_applications >= MAX_APPLICATIONS_PER_DAY:
                await channel.send("⏸️ **Daily limit ho gaya!** Kal subah phir shuru karunga.")
                await asyncio.sleep(3600)
                daily_applications = 0
                continue

            print(f"[{datetime.now().strftime('%H:%M')}] Tasks dhundh raha hoon...")
            bounties = await fetch_open_bounties()
            print(f"Total bounties: {len(bounties)}")

            for b in bounties:
                if not isinstance(b, dict):
                    continue
                if b.get('id') in applied_tasks:
                    continue
                if b.get('status') != 'open':
                    continue
                if b.get('price', 0) < MIN_TASK_PRICE:
                    continue

                # AI decide kare lena chahiye ya nahi
                take, reason, confidence = should_take_task(
                    b.get('title', ''),
                    b.get('description', ''),
                    b.get('price', 0)
                )

                if not take or confidence < 6:
                    print(f"Skip: {b.get('title')} — {reason}")
                    applied_tasks.add(b.get('id'))
                    continue

                # Cover letter banao
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
                embed.add_field(name="🤖 AI Score", value=f"{confidence}/10 — {reason}", inline=False)
                embed.add_field(name="📝 Task", value=str(b.get('description', ''))[:300] + "...", inline=False)
                embed.add_field(name="✉️ Cover Letter", value=cover_letter[:500], inline=False)
                embed.set_footer(text="✅ = Apply karo  |  ❌ = Skip karo")

                msg = await channel.send(embed=embed)
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")
                pending_approvals[msg.id] = {'task': b, 'cover_letter': cover_letter}
                await asyncio.sleep(random.randint(30, 90))

        except Exception as e:
            print(f"Hunt error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

async def check_accepted_tasks():
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
                    await channel.send(
                        f"🎉 **Task Accept Ho Gaya!**\n"
                        f"**{task.get('title')}** — ${task.get('price')}\n"
                        f"⏳ Kaam shuru kar raha hoon..."
                    )
                    asyncio.create_task(do_task_work(task, channel))
        except Exception as e:
            print(f"Accepted check error: {e}")

        await asyncio.sleep(10 * 60)

async def do_task_work(task: dict, channel):
    bounty_id = task.get('id')
    title = task.get('title', '')
    description = task.get('description', '')

    await channel.send(f"🤖 **Kaam kar raha hoon:** {title}\nThoda wait karo...")
    await asyncio.sleep(random.randint(60, 180))

    try:
        result = do_research_task(
            f"Task Title: {title}\n\nTask Description: {description}"
        )

        embed = discord.Embed(
            title=f"📋 Kaam Taiyar — Review Karo!",
            description=f"**Task:** {title}",
            color=0xf39c12
        )
        preview = result[:800] + "\n\n...(poora kaam upload mein jayega)" if len(result) > 800 else result
        embed.add_field(name="📄 Preview", value=preview, inline=False)
        embed.add_field(name="💰 Reward", value=f"${task.get('price', '?')}", inline=True)
        embed.set_footer(text="✅ = Upload  |  ❌ = Dobara karo  |  ✏️ = Edit karke upload")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await msg.add_reaction("✏️")

        pending_work_review[msg.id] = {
            'task': task,
            'result': result,
            'bounty_id': bounty_id
        }

    except Exception as e:
        await channel.send(f"❌ **Error:** {title}\n`{str(e)}`")

@client.event
async def on_ready():
    print(f"✅ Bot ready! {client.user}")
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(
            "🤖 **RentAHuman Bot Online!**\n\n"
            "🔍 Har 15 min — smart task hunting\n"
            "🧠 AI decide karega konsa task lena hai\n"
            "💬 Client questions ka human reply\n"
            "📋 Kaam ready hone pe review maangunga\n\n"
            "**Commands:** `!status` | `!help` | `!reply <message>`"
        )

@client.event
async def on_reaction_add(reaction, user):
    global daily_applications
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
                await channel.send(
                    f"✅ **Apply ho gaya!**\n"
                    f"Task: **{task.get('title')}**\n"
                    f"Price: **${task.get('price')}**\n"
                    f"Aaj ke applications: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}"
                )
            else:
                await channel.send(f"❌ Apply fail — manually check karo: **{task.get('title')}**")

        elif emoji == "❌":
            applied_tasks.add(task['id'])
            await channel.send(f"⏭️ Skip: **{task.get('title')}**")

    elif msg_id in pending_work_review:
        data = pending_work_review.pop(msg_id)
        task = data['task']
        result = data['result']
        bounty_id = data['bounty_id']

        if emoji == "✅":
            await channel.send(f"📤 Upload kar raha hoon: **{task.get('title')}**...")
            await asyncio.sleep(random.randint(3, 8))
            success = await submit_work(bounty_id, result)
            if success:
                active_tasks.pop(bounty_id, None)
                await channel.send(
                    f"🎊 **Submit Ho Gaya!**\n"
                    f"Task: **{task.get('title')}**\n"
                    f"💰 Payment ka wait karo!"
                )
            else:
                await channel.send(f"❌ Submit fail — manually check karo!")

        elif emoji == "❌":
            await channel.send(f"🔄 Dobara kar raha hoon...")
            asyncio.create_task(do_task_work(task, channel))

        elif emoji == "✏️":
            await channel.send(
                f"✏️ Edit karo phir likho:\n"
                f"`!submit {bounty_id}` aur edited text"
            )
            chunks = [result[i:i+1800] for i in range(0, len(result), 1800)]
            for chunk in chunks:
                await channel.send(f"```\n{chunk}\n```")
            pending_work_review[msg_id] = data

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Client ka message aya — human reply generate karo
    if message.content.startswith("!reply "):
        client_msg = message.content.replace("!reply ", "", 1)
        reply = reply_to_client_message(client_msg)
        await message.channel.send(
            f"💬 **Client Ko Ye Reply Bhejo:**\n"
            f"```\n{reply}\n```"
        )

    elif message.content.startswith("!submit "):
        parts = message.content.split(" ", 2)
        if len(parts) >= 3:
            bounty_id = parts[1]
            edited_text = parts[2]
            await message.channel.send(f"📤 Edited kaam upload kar raha hoon...")
            success = await submit_work(bounty_id, edited_text)
            if success:
                active_tasks.pop(bounty_id, None)
                await message.channel.send(f"🎊 **Submit ho gaya!** 💰")
            else:
                await message.channel.send(f"❌ Submit fail")

    elif message.content.lower() == "!status":
        await message.channel.send(
            f"📊 **Status:**\n"
            f"✅ Aaj apply: {daily_applications}/{MAX_APPLICATIONS_PER_DAY}\n"
            f"🔨 Active tasks: {len(active_tasks)}\n"
            f"⏳ Apply pending: {len(pending_approvals)}\n"
            f"📋 Review pending: {len(pending_work_review)}"
        )

    elif message.content.lower() == "!help":
        await message.channel.send(
            "🤖 **Commands:**\n"
            "`!status` — Report dekho\n"
            "`!reply <client ka message>` — Human reply generate karo\n"
            "`!submit <id> <text>` — Edited kaam submit karo\n\n"
            "**Reactions:**\n"
            "✅ Apply / Upload\n"
            "❌ Skip / Dobara\n"
            "✏️ Edit karke upload"
        )

async def main():
    async with client:
        asyncio.ensure_future(hunt_tasks())
        asyncio.ensure_future(check_accepted_tasks())
        await client.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
