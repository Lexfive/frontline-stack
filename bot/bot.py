import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import datetime
from supabase import create_client, Client
import threading
from flask import Flask
import aiohttp
import json

# ================= CONFIGURAÇÃO WEB (FLASK PARA RENDER) =================
app = Flask('')

@app.route('/')
def home():
    return "FRONTLINE BOT ONLINE", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================= CONFIGURAÇÃO DO SISTEMA =================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
VAULT_PATH = "obsidian_vault"

# Configuração Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração Ollama (IA)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = "llama3.2:1b" # Modelo peso-pena ativado

# ================= INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


# ================= MÓDULO DE INTELIGÊNCIA (OLLAMA OTIMIZADO) =================
async def analyze_with_ai(msg_type, content, user):
    """Envia o dado para o Ollama processar via túnel com limites de hardware"""
    
    # 🚨 SYSTEM PROMPT REFINADO PARA MODELOS LEVES (1B)
    system_prompt = """VOCÊ É O NÚCLEO TÁTICO FRONTLINE.
REGRAS: RESPOSTA CURTA, DIRETA, SEM SAUDAÇÕES.
FORMATO:
**DIAGNÓSTICO**
> [Prioridade] - [Viabilidade]
**PLANO:**
- [ ] [Ação 1]
- [ ] [Ação 2]"""

    full_prompt = f"{system_prompt}\n\n[USER: {user} | TYPE: {msg_type.upper()}]\nCONTEÚDO: {content}\n\nANÁLISE:"

    # 🚀 PAYLOAD COM LIMITES DE DESEMPENHO (O segredo para não travar o PC)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "num_thread": 2,       # Usa apenas 2 núcleos do processador
            "num_ctx": 1024,       # Limita uso de memória RAM (contexto curto)
            "num_predict": 300,    # Evita que a IA divague (resposta rápida)
            "temperature": 0.4     # Deixa a IA mais focada e menos "criativa"
        }
    }

    # BYPASS DO NGROK
    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
    }

    try:
        # Timeout de segurança aumentado para evitar erros em CPU
        timeout_config = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(OLLAMA_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "⚠️ Nenhuma resposta gerada.")
                else:
                    texto_erro = await response.text()
                    return f"❌ Erro de conexão com Ollama: HTTP {response.status} - {texto_erro}"
    except aiohttp.ClientConnectorError:
        return "🔌 IA Offline: O túnel (Ngrok) ou o Ollama estão desligados."
    except Exception as e:
        return f"⚠️ Erro na IA: {e}"


# ================= MÓDULO DE PERSISTÊNCIA =================
def save_to_obsidian(message, msg_type, clean_content):
    """Salva o conteúdo formatado no Vault do Obsidian"""
    user = message.author.name
    channel = message.channel.name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    date_today = datetime.datetime.now().strftime("%Y-%m-%d")

    type_folders = {
        "idea": "Ideas",
        "task": "Tasks",
        "bug": "Bugs",
        "log": "Logs"
    }
    folder_name = type_folders.get(msg_type, "Logs")
    
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
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

async def process_event(message):
    """Processa a mensagem, classifica e salva no pipeline"""
    content = message.content
    msg_type = "log"
    
    if content.lower().startswith("!idea"):
        msg_type = "idea"
        content = content.replace("!idea", "").strip()
    elif content.lower().startswith("!task"):
        msg_type = "task"
        content = content.replace("!task", "").strip()
    elif content.lower().startswith("!bug"):
        msg_type = "bug"
        content = content.replace("!bug", "").strip()

    # 1. Persistência no Supabase
    try:
        data = {
            "type": msg_type,
            "content": content,
            "user_name": message.author.name,
            "channel_name": message.channel.name,
            "status": "open"
        }
        supabase.table("events").insert(data).execute()
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")

    # 2. Persistência no Obsidian
    save_to_obsidian(message, msg_type, content)
    return msg_type


# ================= EVENTOS DO BOT =================
@bot.event
async def on_ready():
    print(f"🚀 FRONTLINE ONLINE: {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    """Ignora o erro de comando não encontrado para não sujar o log"""
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Processa comandos de evento (!idea, !task, !bug)
    if any(message.content.startswith(p) for p in ["!idea", "!task", "!bug"]):
        # 1. Salva no banco de dados
        msg_type = await process_event(message)
        emoji = {"idea": "💡", "task": "✅", "bug": "🪲"}.get(msg_type, "📝")
        await message.add_reaction(emoji)
        
        # 2. Chama a IA via túnel e responde
        async with message.channel.typing():
            content = message.content.replace(f"!{msg_type}", "").strip()
            ai_response = await analyze_with_ai(msg_type, content, message.author.name)
            await message.reply(f"🤖 **Análise FRONTLINE:**\n\n{ai_response}")
    
    # Processa comandos normais do discord.py
    await bot.process_commands(message)


# ================= EXECUÇÃO =================
if __name__ == "__main__":
    # Inicia o servidor Flask em Background
    print("🌐 Iniciando Health Check Server...")
    threading.Thread(target=run_web, daemon=True).start()
    
    # Inicia o Bot
    bot.run(TOKEN)
