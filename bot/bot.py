import discord
import json
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import datetime

# ================= CONFIG =================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

VAULT_PATH = "obsidian_vault"

# ================= INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= READY =================
@bot.event
async def on_ready():
    print(f"🚀 FRONTLINE online como {bot.user}")

# ================= OBSIDIAN SYNC =================
def save_to_obsidian(message):
    user = message.author.name
    channel = message.channel.name
    content = message.content
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    user_folder = f"{VAULT_PATH}/Members/{user}"
    channel_folder = f"{VAULT_PATH}/Channels/{channel}"

    os.makedirs(user_folder, exist_ok=True)
    os.makedirs(channel_folder, exist_ok=True)

    filename = f"{timestamp}.md"
    filepath = os.path.join(channel_folder, filename)

    md_content = f"""---
user: {user}
channel: {channel}
timestamp: {timestamp}
---

# 💬 Mensagem

{content}

---

## 🔗 Conexões
- [[{user}]]
- [[{channel}]]
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    user_profile = f"{user_folder}/{user}.md"

    if not os.path.exists(user_profile):
        with open(user_profile, "w", encoding="utf-8") as f:
            f.write(f"# 👤 {user}\n\n## Interações\n")

# ================= AUTO SYNC =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    save_to_obsidian(message)

    await bot.process_commands(message)

# ================= SETUP FULL =================
@bot.command(name="setup_full")
@commands.has_permissions(administrator=True)
async def setup_full(ctx):
    guild = ctx.guild

    await ctx.send("🚀 Criando FRONTLINE completo...")

    roles_config = [
        ("👑 Founder", 0xC9A227),
        ("🧠 Core Team", 0xE8B923),
        ("💼 Investor", 0xA67C00),
        ("🤝 Partner", 0xFFD700),
        ("👤 Member", 0xFFFFFF)
    ]

    created_roles = {}

    for name, color in roles_config:
        role = discord.utils.get(guild.roles, name=name)

        if not role:
            role = await guild.create_role(
                name=name,
                color=discord.Color(color),
                hoist=True
            )

        created_roles[name] = role

    cat_inst = await guild.create_category("📢 INSTITUCIONAL")
    cat_com = await guild.create_category("💬 COMUNIDADE")
    cat_val = await guild.create_category("📊 VALOR")
    cat_voice = await guild.create_category("🎙 VOZ")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        created_roles["🧠 Core Team"]: discord.PermissionOverwrite(read_messages=True),
        created_roles["👑 Founder"]: discord.PermissionOverwrite(read_messages=True)
    }

    cat_team = await guild.create_category("🔒 EQUIPE", overwrites=overwrites)

    async def create_channel(category, name, content):
        ch = await category.create_text_channel(name)
        await ch.send(content)
        return ch

    start = await create_channel(cat_inst, "start-here", """
# 🚀 FRONTLINE

Sistema de networking e negócios.

---

## 🎯 Escolha seu perfil

💼 Investor  
🤝 Partner  
🧠 Core Team  
👤 Member  

---
Sem valor = sem espaço.
""")

    await create_channel(cat_inst, "rules", "Respeito + valor. Sem spam.")
    await create_channel(cat_inst, "announcements", "Atualizações oficiais.")
    await create_channel(cat_inst, "roadmap", "Crescimento do projeto.")

    await create_channel(cat_com, "general", "Conversa geral.")
    await create_channel(cat_com, "network", "Apresente-se.")
    await create_channel(cat_com, "questions", "Dúvidas.")
    await create_channel(cat_com, "feedback", "Sugestões.")

    await create_channel(cat_val, "opportunities", """
## 📊 OPORTUNIDADES

- Tipo:
- Valor:
- Quem precisa:
""")

    await create_channel(cat_val, "results", "Resultados reais.")
    await create_channel(cat_val, "insights", "Conhecimento estratégico.")
    await create_channel(cat_val, "resources", "Ferramentas úteis.")

    await cat_voice.create_voice_channel("💼 Business Call")
    await cat_voice.create_voice_channel("🌐 Networking")

    await cat_team.create_text_channel("internal")
    await cat_team.create_text_channel("strategy")
    await cat_team.create_text_channel("growth")
    await cat_team.create_text_channel("finance")
    await cat_team.create_text_channel("tech")

    msg = await start.send("Reaja para receber seu cargo:")

    emojis = {
        "💼": "💼 Investor",
        "🤝": "🤝 Partner",
        "🧠": "🧠 Core Team",
        "👤": "👤 Member"
    }

    for emoji in emojis:
        await msg.add_reaction(emoji)

    bot.reaction_message_id = msg.id

    await ctx.send("✅ FRONTLINE criado com sucesso!")

# ================= APPLY TEMPLATE =================
@bot.command(name="apply_template")
@commands.has_permissions(administrator=True)
async def apply_template(ctx):
    guild = ctx.guild

    await ctx.send("⚙️ Aplicando template...")

    with open("templates/frontline.json", "r", encoding="utf-8") as f:
        template = json.load(f)

    for r in template["roles"]:
        role = discord.utils.get(guild.roles, name=r["name"])

        if not role:
            await guild.create_role(
                name=r["name"],
                color=discord.Color(r["color"]),
                hoist=True
            )

    for cat_data in template["categories"]:
        category = discord.utils.get(guild.categories, name=cat_data["name"])

        if not category:
            category = await guild.create_category(cat_data["name"])

        for ch_data in cat_data["channels"]:
            channel = discord.utils.get(category.text_channels, name=ch_data["name"])

            if not channel:
                channel = await category.create_text_channel(ch_data["name"])
                await channel.send(ch_data["message"])

    await ctx.send("✅ Template aplicado!")

# ================= NUKE SERVER =================
@bot.command(name="nuke_server")
@commands.has_permissions(administrator=True)
async def nuke_server(ctx, confirm: str = None):
    if confirm != "CONFIRMAR":
        await ctx.send("⚠️ Use: !nuke_server CONFIRMAR")
        return

    guild = ctx.guild

    await ctx.send("💣 Limpando em 3 segundos...")
    await asyncio.sleep(3)

    for channel in list(guild.channels):
        try:
            await channel.delete()
            await asyncio.sleep(0.2)
        except:
            pass

    for role in list(guild.roles):
        if role.name == "@everyone" or role.managed:
            continue

        try:
            await role.delete()
            await asyncio.sleep(0.2)
        except:
            pass

    print("☠️ Limpeza completa.")

# ================= REACTION ROLE =================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != getattr(bot, "reaction_message_id", None):
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if member is None or member.bot:
        return

    emoji = str(payload.emoji)

    role_map = {
        "💼": "💼 Investor",
        "🤝": "🤝 Partner",
        "🧠": "🧠 Core Team",
        "👤": "👤 Member"
    }

    role_name = role_map.get(emoji)

    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)

        if role:
            await member.add_roles(role)

# ================= RUN =================
bot.run(TOKEN)