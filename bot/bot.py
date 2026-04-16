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
# ================= MÓDULO DE INTELIGÊNCIA (OLLAMA CHAT API) =================
async def analyze_with_ai(msg_type, content, user):
    """Envia o dado para o Ollama processar usando a API de Chat (Personalidade DevOps)"""
    
    # 🚨 O novo endpoint correto para o modo "messages"
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    
    # 🧠 PERSONALIDADE FRONTLINE
    system_prompt = """Você é um assistente técnico avançado chamado Frontline.
Regras de comportamento:
- Responda sempre em português do Brasil (PT-BR).
- Seja direto, objetivo e prático. Evite enrolação e respostas longas.
- Use linguagem clara, mas com precisão técnica. Pense como um DevOps ao responder.
- Trate o usuário como "Lexfive".
- Se a pergunta for simples, responda curto. Se for complexa, explique de forma estruturada.
- Tom profissional, confiante e focado em resolver rápido o problema.
- NUNCA invente informações. Se não souber, diga.
- Vá direto ao ponto, sem saudações (não diga "olá", "claro", "aqui está").

FORMATO DE RESPOSTA OBRIGATÓRIO (para registros técnicos):
- Use listas ou bullet points.
- Destaque comandos ou instruções claramente."""

    # Configuração rígida de limite para não travar a máquina
    payload = {
        "model": OLLAMA_MODEL, # Vai usar o modelo que definimos no topo do bot.py (llama3.2:1b)
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Ação [{msg_type.upper()}]: {content}"}
        ],
        "stream": False,
        "options": {
            "num_thread": 2,       # Mantém o PC livre
            "num_predict": 250,    # 🚨 LIMITADOR: Impede que o bot fale demais e trave
            "temperature": 0.3     # IA focada e fria
        }
    }

    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
    }

    try:
        timeout_config = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(chat_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # A API de chat devolve a resposta em um local diferente do JSON
                    return data.get("message", {}).get("content", "⚠️ Nenhuma resposta gerada.")
                else:
                    texto_erro = await response.text()
                    return f"❌ Erro de conexão HTTP {response.status} - {texto_erro}"
    except Exception as e:
        return f"🔌 Erro Crítico de Comunicação IA: {e}"
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
    
    # Nova lista de comandos táticos
    comandos_validos = ["!idea", "!task", "!bug", "!log", "!intel", "!sos"]
    
    for cmd in comandos_validos:
        if content.lower().startswith(cmd):
            msg_type = cmd.replace("!", "") # Extrai o tipo (ex: "intel")
            content = content[len(cmd):].strip() # Limpa o comando do texto
            break

    # Persistência no Supabase
    try:
        data = {
            "type": msg_type,
            "content": content,
            "user_name": message.author.name,
            "channel_name": message.channel.name,
            "status": "open" if msg_type != "log" else "archived" # Logs já nascem arquivados
        }
        supabase.table("events").insert(data).execute()
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")

    return msg_type

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
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    comandos_taticos = ["!idea", "!task", "!bug", "!log", "!intel", "!sos"]

    # Processa os comandos que vão para o Banco de Dados
    if any(message.content.lower().startswith(p) for p in comandos_taticos):
        # 1. Salva no banco de dados
        msg_type = await process_event(message)
        
        # Dicionário de Emojis atualizado
        emojis = {"idea": "💡", "task": "✅", "bug": "🪲", "log": "📝", "intel": "👁️", "sos": "🚨"}
        emoji = emojis.get(msg_type, "⚙️")
        await message.add_reaction(emoji)
        
        # 2. Chama a IA via túnel (Apenas se não for um simples log/intel)
        if msg_type not in ["log", "intel"]:
            async with message.channel.typing():
                content = message.content.split(" ", 1)[1] if " " in message.content else message.content
                ai_response = await analyze_with_ai(msg_type, content, message.author.name)
                await message.reply(f"🤖 **Análise FRONTLINE:**\n\n{ai_response}")
        else:
            await message.reply(f"{emoji} **Registro '{msg_type.upper()}' arquivado com sucesso no Supabase.**")
            
        return # Impede que ele tente ler como comando normal do discord

    # Processa comandos normais do bot (como o !status que faremos abaixo)
    await bot.process_commands(message)
    
    # Processa comandos normais do discord.py
    await bot.process_commands(message)

@bot.command(name="status")
async def system_status(ctx):
    """Checa se o PC local e a IA estão respondendo"""
    msg = await ctx.send("📡 **Pulsando servidores locais...**")
    
    try:
        # Tenta bater no servidor Ollama da sua casa via Ngrok
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(OLLAMA_URL.replace("/api/generate", ""), headers={"ngrok-skip-browser-warning": "true"}) as response:
                if response.status == 200:
                    await msg.edit(content="🟢 **STATUS DO SISTEMA: OPERACIONAL**\n- Nuvem (Render): OK\n- Banco (Supabase): OK\n- Túnel (Ngrok): Conectado\n- IA Local (Ollama): Respondendo")
                else:
                    await msg.edit(content=f"🟡 **STATUS DO SISTEMA: DEGRADADO**\n- Nuvem: OK\n- IA Local: Erro HTTP {response.status}")
    except Exception:
        await msg.edit(content="🔴 **STATUS DO SISTEMA: CRÍTICO**\n- Nuvem (Render): OK\n- Túnel/IA Local: **DESCONECTADO**. Verifique o Ngrok no PC-Base.")


# ================= EXECUÇÃO =================
if __name__ == "__main__":
    # Inicia o servidor Flask em Background
    print("🌐 Iniciando Health Check Server...")
    threading.Thread(target=run_web, daemon=True).start()
    
    # Inicia o Bot
    bot.run(TOKEN)
