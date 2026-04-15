import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import datetime
from supabase import create_client, Client

# ================= CONFIGURAÇÃO =================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
VAULT_PATH = "obsidian_vault"

# Configuração Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= MÓDULO DE PERSISTÊNCIA (SUPABASE & OBSIDIAN) =================

def save_to_obsidian(message, msg_type, clean_content):
    """Salva o conteúdo formatado no Vault do Obsidian"""
    user = message.author.name
    channel = message.channel.name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    date_today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Define a pasta com base no tipo (Organização automática)
    type_folders = {
        "idea": "Ideas",
        "task": "Tasks",
        "bug": "Bugs",
        "log": "Logs"
    }
    folder_name = type_folders.get(msg_type, "Logs")
    
    # Caminhos: obsidian_vault/Tasks/2026-04-15/nome_arquivo.md
    target_dir = os.path.join(VAULT_PATH, folder_name, date_today)
    os.makedirs(target_dir, exist_ok=True)

    filename = f"{timestamp}_{user}.md"
    filepath = os.path.join(target_dir, filename)

    md_content = f"""---
type: {msg_type}
user: {user}
channel: {channel}
timestamp: {timestamp}
status: open
---

# 📥 Entrada: {msg_type.upper()}

{clean_content}

---
## 🔗 Conexões
- [[{user}]]
- [[{channel}]]
- [[{date_today}]]
- [[{folder_name}]]
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

async def process_event(message):
    """Processa a mensagem, classifica e salva no pipeline"""
    content = message.content
    msg_type = "log"
    
    # Classificador de Prefixo
    if content.lower().startswith("!idea"):
        msg_type = "idea"
        content = content.replace("!idea", "").strip()
    elif content.lower().startswith("!task"):
        msg_type = "task"
        content = content.replace("!task", "").strip()
    elif content.lower().startswith("!bug"):
        msg_type = "bug"
        content = content.replace("!bug", "").strip()

    # 1. Persistência no Supabase (Estado Vivo)
    try:
        data = {
            "type": msg_type,
            "content": content,
            "user_name": message.author.name,
            "channel_name": message.channel.name,
            "status": "open",
            "priority": "medium"
        }
        supabase.table("events").insert(data).execute()
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")

    # 2. Persistência no Obsidian (Memória de Longo Prazo)
    save_to_obsidian(message, msg_type, content)
    
    return msg_type

# ================= EVENTOS DO BOT =================

@bot.event
async def on_ready():
    print(f"🚀 FRONTLINE BOT PROJECT online como {bot.user}")
    print(f"🧠 Pipeline Obsidian: {VAULT_PATH}")
    print(f"🗄️ Supabase: Conectado")

@bot.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return

    # Se a mensagem começar com um dos prefixos de comando de evento
    if any(message.content.startswith(p) for p in ["!idea", "!task", "!bug"]):
        msg_type = await process_event(message)
        emoji = {"idea": "💡", "task": "✅", "bug": "🪲"}.get(msg_type, "📝")
        await message.add_reaction(emoji)
    
    # Processa outros comandos (como !nuke_server)
    await bot.process_commands(message)

# ================= COMANDOS ADMINISTRATIVOS =================

@bot.command(name="nuke_server")
@commands.has_permissions(administrator=True)
async def nuke_server(ctx, confirm: str = None):
    if confirm != "CONFIRMAR":
        await ctx.send("⚠️ Use: `!nuke_server CONFIRMAR` para limpar o servidor.")
        return

    await ctx.send("💣 Iniciando limpeza total em 3 segundos...")
    await asyncio.sleep(3)

    for channel in list(ctx.guild.channels):
        try:
            await channel.delete()
        except: continue

    for role in list(ctx.guild.roles):
        if role.name != "@everyone" and not role.managed:
            try:
                await role.delete()
            except: continue

    print("☠️ Servidor resetado.")

# ================= REACTION ROLES =================

@bot.event
async def on_raw_reaction_add(payload):
    # Lógica de cargos por reação (ajuste o ID da mensagem se necessário)
    role_map = {
        "💼": "💼 Investor",
        "🤝": "🤝 Partner",
        "🧠": "🧠 Core Team",
        "👤": "👤 Member"
    }
    
    emoji = str(payload.emoji)
    if emoji in role_map:
        guild = bot.get_guild(payload.guild_id)
        role = discord.utils.get(guild.roles, name=role_map[emoji])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_role(role)

# ================= EXECUÇÃO =================
if __name__ == "__main__":
    bot.run(TOKEN)
