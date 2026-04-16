import os
import requests
import re
import time

# ================= CONFIGURAÇÕES =================
SUPABASE_URL = "SUA_URL_AQUI"
SUPABASE_KEY = "SUA_CHAVE_AQUI"
OBSIDIAN_VAULT_PATH = "./00_Inbox_Frontline"
# =================================================

def limpar_nome(texto):
    """Limpa o texto para criar um nome de arquivo válido e curto"""
    limpo = re.sub(r'[\\/*?:"<>|]', "", texto)
    return limpo[:25].strip().replace(" ", "_")

def atualizar_yaml_confirmados(file_path, novos_confirmados):
    """Lê o arquivo local, atualiza a lista de confirmados no Frontmatter e não quebra o resto do arquivo"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        partes = content.split("---")
        if len(partes) < 3:
            return # Arquivo não tem a estrutura YAML esperada

        frontmatter = partes[1]
        body = "---".join(partes[2:])

        # Isola e limpa os confirmados antigos
        linhas = frontmatter.strip().split("\n")
        novas_linhas = []
        pulando_lista = False

        for linha in linhas:
            if linha.startswith("confirmados:"):
                pulando_lista = True
                continue
            if pulando_lista and linha.startswith("  -"):
                continue
            pulando_lista = False
            novas_linhas.append(linha)

        # Injeta a lista atualizada do banco de dados
        novas_linhas.append("confirmados:")
        if novos_confirmados:
            for user in novos_confirmados:
                novas_linhas.append(f"  - {user}")
        else:
            novas_linhas.append("  []")

        novo_frontmatter = "\n".join(novas_linhas) + "\n"
        novo_conteudo = f"---\n{novo_frontmatter}---{body}"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(novo_conteudo)

    except Exception as e:
        pass # Falha silenciosa para não quebrar o loop

def sync_tasks():
    endpoint = f"{SUPABASE_URL}/rest/v1/events?select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.status_code != 200:
            return
            
        dados = response.json()
        
        if not os.path.exists(OBSIDIAN_VAULT_PATH):
            os.makedirs(OBSIDIAN_VAULT_PATH)

        icones = {"IDEA": "💡", "BUG": "🪲", "TASK": "✅", "LOG": "📝", "INTEL": "👁️", "SOS": "🚨", "EVENTO": "📅"}
        callouts = {"IDEA": "example", "BUG": "bug", "TASK": "todo", "LOG": "info", "INTEL": "quote", "SOS": "warning", "EVENTO": "calendar"}

        for record in dados:
            item_id = str(record.get('id', '000'))
            item_type = record.get('type', 'log').upper()
            content = record.get('content', 'Sem conteúdo')
            
            # TRUQUE DE ENGENHARIA: Extrai os confirmados do texto sem precisar alterar tabelas no banco de dados
            confirmados = []
            if "CONFIRMADOS:" in content:
                partes = content.split("CONFIRMADOS:")
                content = partes[0].strip() # O conteúdo real volta a ser só o texto
                users_str = partes[1].strip()
                if users_str:
                    confirmados = [u.strip() for u in users_str.split(",") if u.strip()]
            
            id_curto = item_id.split('-')[0][:5]
            resumo = limpar_nome(content)
            file_name = f"{item_type}_{resumo}_{id_curto}.md"
            
            file_path = os.path.join(OBSIDIAN_VAULT_PATH, file_name)
            
            # Se o arquivo JÁ EXISTE, não cria um novo. Apenas atualiza a lista de confirmados.
            if os.path.exists(file_path):
                if item_type == "EVENTO":
                    atualizar_yaml_confirmados(file_path, confirmados)
                continue

            icone = icones.get(item_type, "📌")
            caixa_visual = callouts.get(item_type, "note")

            # Formata a string do YAML para o momento da criação do arquivo
            lista_yaml = "\n".join([f"  - {u}" for u in confirmados]) if confirmados else "  []"

            markdown_content = f"""---
type: {record.get('type')}
user: {record.get('user_name')}
channel: {record.get('channel_name')}
status: {record.get('status')}
id_origin: {item_id}
confirmados:
{lista_yaml}
---
# {icone} Entrada: {item_type}

> [!{caixa_visual}] **Registro do Operador | {record.get('user_name')}**
> {content}

---
### 🛠️ Espaço Tático
- [ ] Revisar entrada
- [ ] Iniciar execução

---
## 🔗 Conexões
#frontline #{record.get('type')}
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

    except Exception:
        pass 

if __name__ == "__main__":
    while True:
        sync_tasks()
        time.sleep(300)
