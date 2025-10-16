import os
import re
import sys
import json
import uuid
import hashlib
import tempfile
import requests
import tiktoken
from openai import OpenAI
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv


from urllib.parse import urljoin, urlparse, urlunparse
from flask import Flask, request, jsonify
from flask_cors import CORS


from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from pydub import AudioSegment

from langchain_chroma import Chroma 
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings

from dialog_manager import DialogManager
#import double


# Desativar telemetria
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False'

# CONFIGURAR TIKTOKEN NO EXECUTÁVEL
if getattr(sys, 'frozen', False):
    # Executável PyInstaller
    TEMP_PATH = sys._MEIPASS  # Ficheiros temporários (tiktoken)
    BASE_DIR = os.path.dirname(sys.executable)  # Pasta persistente
    
    # Configurar tiktoken
    tiktoken_path = os.path.join(TEMP_PATH, 'tiktoken_ext', 'openai_public')
    if os.path.exists(tiktoken_path):
        os.environ['TIKTOKEN_CACHE_DIR'] = tiktoken_path
        print(f"Tiktoken: {tiktoken_path}")
        files = [f for f in os.listdir(tiktoken_path) if f.endswith('.tiktoken')]
        print(f"Ficheiros: {files}")
    else:
        print(f"Tiktoken não encontrado em {tiktoken_path}")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"Base path: {BASE_DIR}")

# PASTAS PERSISTENTES
HISTORY_FOLDER = os.path.join(BASE_DIR, "history")
SAVE_FOLDER = os.path.join(BASE_DIR, "scraped_pages")
TAG_FOLDER = os.path.join(BASE_DIR, "tag_freq")
TITLES_FOLDER = os.path.join(BASE_DIR, "conversation_titles")

# Criar pastas
for folder in [HISTORY_FOLDER, SAVE_FOLDER, TAG_FOLDER, TITLES_FOLDER]:
    os.makedirs(folder, exist_ok=True)
    print(f"Pasta: {folder}")

# Ficheiros
JSON_FILE = os.path.join(SAVE_FOLDER, "pagina_scraped.json")
TAG_FREQ_FILE = os.path.join(TAG_FOLDER, "tag_freq.json")
TITLES_FILE = os.path.join(TITLES_FOLDER, "conversation_titles.json")

news_index_map = {}

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A API_KEY não está definida.")

client = OpenAI(api_key = openai_api_key)

dialog_manager = DialogManager()


API_CONFIG = {
    #"model": "gpt-3.5-turbo",
    "model": "gpt-4.1-mini-2025-04-14",
    "temp": 0.7
}

system_prompt_informativo = (
    "És um assistente virtual projetado para ajudar pessoas com deficiências visuais a entenderem o conteúdo das páginas da web. "
    "A tua função é ajudar estas pessoas a navegarem e a extrairem informações sobre a página web onde se encontram.\n\n"
    "A estrutura de mensagem deve ser assim: 1. Título da notícia — descrição... — link da notícia 2. Título da segunda notícia — descrição... — link da notícia, e por ai em diante"
    "- No máximo 3 ou 4 notícias por resposta. A não ser que o user peça um número especifico, ai das o número que o user pediu\n"
)
#"Quanto menor o valor da Order, maior a página dá destaque a essa notícia"
#"Quando encontras várias notícias relacionadas com o mesmo tema, resume todas elas de forma natural, em estilo de conversa, sem repetir a mesma notícia várias vezes. Se houver duas ou três notícias diferentes, menciona todas numa só resposta."

system_prompt_conversacional = (
    "OBJECTIVO: Partilhar notícias de forma rápida e natural, como se estivesses a conversar com um amigo.\n\n"

    "TOM E ESTILO:\n"
    "- Usa linguagem simples e formal, sem parecer um robô.\n"
    "- Fala em frases curtas, diretas\n"

    "COMO DAR NOTÍCIAS:\n"
    "- No máximo 3 ou 4 notícias por resposta. A não ser que o user peça um número especifico, ai das o número que o user pediu\n"
    "- Mas se o utilizador pedir explicitamente um número de notícias (ex: 'dá-me 10 notícias'), deves respeitar esse número até ao limite do que tens disponível.\n"
    "- Ao apresentares as notícias, conta um pouco soubre a notícia em algumas frases. Para que o user tenha um ouco de contexto do que é que a notícia se trata\n"
    "- Interliga as notícias com frases de transição, de forma a tornar a conversa mais notural e menos robotica"

    "INTERAÇÃO:\n"
    "- Faz perguntas curtas para puxar conversa\n"
    "- Se o utilizador mostra interesse num tema, podes dar um pouco mais de detalhe, mas continua direto.\n"
    "- Se fizer sentido, sugere naturalmente outros assuntos.\n\n"
)

#system_prompt_conversacional = (
#    "OBJECTIVO: Partilhar notícias de forma rápida e natural, como se estivesses a conversar com um amigo.\n\n"
#
#    "TOM E ESTILO:\n"
#    "- Usa linguagem simples e descontraída, sem parecer um robô.\n"
#    "- Fala em frases curtas, diretas, como num café ou chamada de telefone.\n"
#    "- Usa expressões comuns (ex: 'Olha', 'Sabes que...', 'Pois é', 'Pelos vistos').\n"
#    "- Mostra reações humanas, mas sem exagerar (ex: 'Uau, isso surpreendeu-me', 'É chato, mas é o que é').\n\n"
#
#    "COMO DAR NOTÍCIAS:\n"
#    "- No máximo 3 ou 4 notícias por resposta.\n"
#    "- Cada notícia deve ser contada em 1 a 2 frases no máximo.\n"
#    "- Se houver mais notícias, diz de forma casual que há mais e pergunta se querem ouvir.\n\n"
#
#    "INTERAÇÃO:\n"
#    "- Faz perguntas curtas para puxar conversa ('Queres saber mais sobre isto?', 'Preferes que fale de política ou de desporto?').\n"
#    "- Se o utilizador mostra interesse num tema, podes dar um pouco mais de detalhe, mas continua direto.\n"
#    "- Se fizer sentido, sugere naturalmente outros assuntos ('Já agora, também vi algo sobre...').\n\n"
#
#    "EM RESUMO:\n"
#    "Tu não és um bot a ler uma lista. És um amigo bem informado a contar as últimas notícias de forma rápida, clara e leve, "
#    "sempre a deixar espaço para continuar a conversa."
#)


def list_conversations():
    if not os.path.exists(HISTORY_FOLDER):
        os.makedirs(HISTORY_FOLDER)
    return [f for f in os.listdir(HISTORY_FOLDER) if f.endswith(".json")]

def load_conversation(filename):
    with open(os.path.join(HISTORY_FOLDER, filename), "r") as file:
        return json.load(file)

def save_conversation(history, filename):
    if not os.path.exists(HISTORY_FOLDER):
        os.makedirs(HISTORY_FOLDER)
    with open(os.path.join(HISTORY_FOLDER, filename), "w") as file:
        json.dump(history, file, indent=2)

def generate_conversation_id():
    return "conversa_" + str(uuid.uuid4())



def get_conversation_vector_store(conversation_id):
    """Versão corrigida para PyInstaller"""
    if conversation_id.endswith(".json"):
        conversation_id = conversation_id[:-5]
    
    # BASE_DIR global
    persist_directory = os.path.join(BASE_DIR, "chroma_store", conversation_id)
    
    print(f"ChromaDB path: {persist_directory}")
    
    # Criar pasta
    try:
        os.makedirs(persist_directory, exist_ok=True)
        print(f"Pasta criada")
    except Exception as e:
        print(f"Erro ao criar pasta: {e}")
        raise
    
    # Testar escrita
    test_file = os.path.join(persist_directory, "test_write.tmp")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print(f"Permissões OK")
    except Exception as e:
        print(f"Sem permissão para escrever: {e}")
        raise
    
    embedding_function = OpenAIEmbeddings(openai_api_key=openai_api_key)

    try:
        vector_store = Chroma(
            collection_name=conversation_id,
            persist_directory=persist_directory,
            embedding_function=embedding_function
        )
        
        print(f"Vector store criado")
        
        # Contar documentos
        try:
            doc_count = vector_store._collection.count()
            print(f"Documentos: {doc_count}")
        except Exception as e:
            print(f"Erro ao contar: {e}")
        
        return vector_store
        
    except Exception as e:
        print(f"Erro ao criar vector store: {e}")
        import traceback
        traceback.print_exc()
        raise




#### title_generator #####

def load_conversation_titles():
    """Carrega os títulos das conversas do ficheiro JSON"""
    if os.path.exists(TITLES_FILE):
        try:
            with open(TITLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar títulos: {e}")
            return {}
    return {}

def save_conversation_titles(titles):
    """Guarda os títulos das conversas no ficheiro JSON"""
    try:
        with open(TITLES_FILE, "w", encoding="utf-8") as f:
            json.dump(titles, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao guardar títulos: {e}")

def generate_conversation_title(bot_response, conversation_id):
    """
    Gera um título para a conversa baseado na primeira pergunta do user 
    e/ou resposta do bot
    """
    urls = get_current_urls(conversation_id)
    if urls:
        site_url = urls[0]
        parsed_url = urlparse(site_url)
        site_url = parsed_url.netloc or site_url

    prompt = (
        f"Resumo da conversa:\n\n"
        f"Resposta do assistente: {bot_response}\n"
        f"Esta conversa está relacionada com o site: {site_url}\n\n"
        f"Gera um título curto (máximo 12 palavras) para identificar esta conversa. E termina sempre o titulo com o nome do site (exemplo: Destaques do Jornaldenegocios)"
        f"O título deve ser claro, informativo e refletir o tema. Evita repetir a pergunta literalmente."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "És um assistente que cria títulos resumidos e descritivos para conversas baseadas em conteúdo."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        title = response.choices[0].message.content.strip()

        titles = load_conversation_titles()
        titles[conversation_id] = title
        save_conversation_titles(titles)

    except Exception as e:
        print(f"Erro ao gerar/guardar o título: {e}")
        return None
    

def get_conversation_title(conversation_id):
    """Obtém o título de uma conversa ou retorna o ID se não existir"""
    titles = load_conversation_titles()
    return titles.get(conversation_id, conversation_id)

def get_all_conversations_with_titles():
    """Retorna todas as conversas com os seus títulos"""
    titles = load_conversation_titles()
    conversations = list_conversations()
    
    result = []
    for conv_file in conversations:
        conv_id = conv_file.replace(".json", "")
        title = titles.get(conv_id, conv_id)
        file_path = os.path.join(HISTORY_FOLDER, conv_file)
        timestamp = os.path.getmtime(file_path)
        result.append({
            "id": conv_id,
            "title": title,
            "filename": conv_file,
            "timestamp": timestamp
        })
    result.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return result
############################################################################

def extrair_categoria_do_link(link):
    """Extrai a categoria do link da notícia."""
    try:
        path = urlparse(link).path.strip("/")
        partes = path.split("/")
        # ignora datas numéricas no início
        partes_sem_datas = [p for p in partes if not p.isdigit() and not (len(p) == 4 and p.isnumeric())]
        if partes_sem_datas:
            return partes_sem_datas[0].lower()
    except Exception:
        return None
    return None

#### chromadb #####
def save_to_chromadb(vector_store, conversation_id, url, text, categories=None):
    print(f"\n{'='*60}")
    print(f"🔍 DEBUG save_to_chromadb")
    print(f"   URL: {url}")
    print(f"   Tamanho do texto: {len(text) if text else 0} caracteres")
    print(f"   Categorias: {len(categories) if categories else 0}")
    print(f"{'='*60}\n")
    
    if not text or len(text.strip()) < 10:
        print("Texto muito curto")
        return False
    
    # --- Guardar categorias COM PROTEÇÃO ---
    if categories is not None:
        print(f"A processar {len(categories)} categorias...")
        
        try:
            category_text = "Categorias encontradas na página:\n" + "\n".join(
                [f"{name.title()}: {link}" for name, link in categories]
            )
            print(f"   Texto das categorias: {len(category_text)} caracteres")
            
            category_hash = hashlib.sha256(f"categorias_{url}".encode("utf-8")).hexdigest()
            print(f"   Hash gerado: {category_hash[:16]}...")

            print("   A verificar se categorias já existem...")
            existing = vector_store._collection.get(
                where={"hash": category_hash}, 
                include=["metadatas"]
            )["metadatas"]
            
            if not existing:
                print("   A criar documento de categorias...")
                doc = Document(
                    page_content=category_text,
                    metadata={
                        "url": url,
                        "conversation_id": conversation_id,
                        "hash": category_hash,
                        "tipo": "categorias",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                print("   A adicionar ao vector store...")
                vector_store.add_documents([doc])
                print("Categorias guardadas")
            else:
                print("Categorias já existem")
                
        except Exception as e:
            print(f"\nERRO AO GUARDAR CATEGORIAS:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {str(e)}")
            import traceback
            print("\nStack trace:")
            traceback.print_exc()
            
            # Continuar mesmo com erro nas categorias
            print("\nA continuar sem categorias...")

    # --- Extrair artigos ---
    print(f"\n A extrair artigos do HTML...")
    
    try:
        soup = BeautifulSoup(text, "html.parser")
        articles = soup.find_all("article")
        print(f"   Encontrados {len(articles)} tags <article>")
    except Exception as e:
        print(f"Erro ao parsear HTML: {e}")
        return False

    if not articles:
        print(" Nenhum <article> encontrado")
        return False

    print(f"\n A processar {len(articles)} artigos...")
    
    try:
        tag_freq = load_tag_freq()
    except Exception as e:
        print(f" Erro ao carregar tag_freq (a usar vazio): {e}")
        tag_freq = {}
    
    docs = []
    skipped_short = 0
    skipped_duplicate = 0

    for order, article in enumerate(articles, start=1):
        try:
            article_html = str(article)
            article_text = article.get_text(" ", strip=True)

            print(f"   [{order}/{len(articles)}] Tamanho: {len(article_text)} chars", end="")

            if len(article_text) < 20:
                print(" → ⏭️ Muito curto")
                skipped_short += 1
                continue
            
            # Hash
            artigo_hash = hashlib.sha256(article_text.encode("utf-8")).hexdigest()
            tag_freq[artigo_hash] = tag_freq.get(artigo_hash, 0) + 1
            
            if tag_freq[artigo_hash] >= DUPLICATE_THRESHOLD:
                print(" → 🔁 Duplicado")
                skipped_duplicate += 1
                continue
            
            # Extrair link
            primeiro_link = None
            article_soup = BeautifulSoup(article_html, "html.parser")
            first_link_tag = article_soup.find("a", href=True)
            
            if first_link_tag:
                primeiro_link = first_link_tag.get("href")
            
            if not primeiro_link:
                urls_encontradas = re.findall(r'https?://\S+', article_html)
                if urls_encontradas:
                    primeiro_link = urls_encontradas[0]
            
            if primeiro_link and not primeiro_link.startswith("http"):
                primeiro_link = urljoin(url, primeiro_link)
            
            tipo_categoria = "Desconhecido"
            if primeiro_link:
                tipo_categoria = extrair_categoria_do_link(primeiro_link) or "Desconhecido"
            
            doc = Document(
                page_content=article_html,
                metadata={
                    "url": url,
                    "hash": artigo_hash,
                    "conversation_id": conversation_id,
                    "Order": order,
                    "tipo_categoria": tipo_categoria,
                    "primeiro_link": primeiro_link or "",
                    "timestamp": datetime.now().isoformat()
                }
            )
            docs.append(doc)
            
        except Exception as e:
            print(f"Erro: {e}")
            continue
    
    try:
        save_tag_freq(tag_freq)
    except Exception as e:
        print(f"Erro ao guardar tag_freq: {e}")
    
    print(f"\nResumo:")
    print(f"   Total: {len(articles)}, Curtos: {skipped_short}, Duplicados: {skipped_duplicate}, Válidos: {len(docs)}")

    if not docs:
        print("\nNenhum artigo válido")
        return True

    print(f"\nA guardar {len(docs)} documentos...")
    
    try:
        vector_store.add_documents(docs)
        print(f"{len(docs)} artigos guardados!\n")
        return True
        
    except Exception as e:
        print(f"\nERRO AO GUARDAR ARTIGOS:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def retrieve_from_chromadb(query, vector_store):
    try:
        results = vector_store.similarity_search(query, k=10)#60/70
    
        results = sorted(
            results,
            key=lambda doc: doc.metadata.get("Order", 999999)
        )
        
        print(f"Documentos relevantes: {len(results)}")
        #retrieved_texts = "\n\n".join([doc.page_content for doc in results])
        retrieved_texts = "\n\n".join(
            [f"[Order {doc.metadata.get('Order')}] {doc.page_content}" for doc in results]
        )
        
        #retrieved_texts = "\n\n".join([
        #    f"[Order: {doc.metadata.get('Order', '?')}] {doc.page_content}"
        #    for doc in results
        #])

        if not retrieved_texts.strip():
            print("Inf relevante não encontrada")
            return ""
        return retrieved_texts
    except Exception as e:
        print(f"Erro ao recuperar do chromaDB: {str(e)}")
        return ""


def retrieve_from_chromadb_by_order(vector_store, top_n=10):
    try:
        # Obter todos os documentos e metadados
        all_docs = vector_store.get(include=["documents", "metadatas"])
        
        # Juntar conteúdos e metadados
        docs = list(zip(all_docs["documents"], all_docs["metadatas"]))
        
        # Ordenar pelo campo "Order"
        ordered_docs = sorted(
            docs, key=lambda x: x[1].get("Order", 999999)
        )
        
        # Selecionar só os top_n
        selected = ordered_docs[:top_n]
        
        # Montar texto final
        retrieved_texts = "\n\n".join(
            [f"[Order {meta['Order']}] {doc}" for doc, meta in selected]
        )
        return retrieved_texts
    
    except Exception as e:
        print(f"Erro ao recuperar docs por ordem: {str(e)}")
        return ""

####################################################################

#### LINKS #####

def make_links_clickable(text):
    #Extrai os links em formato [texto](URL) -> clicaveis
    url_pattern = re.compile(r'(https?://[^\s]+)')
    return url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', text)

def get_current_urls(conversation_id):
    vector_store = get_conversation_vector_store(conversation_id)
    docs = vector_store.get(include=["metadatas"])
    
    urls = set()
    if docs and "metadatas" in docs:
        for meta in docs["metadatas"]:
            if meta and "url" in meta:
                urls.add(meta["url"])
    
    return list(urls)

####################################################################

#### Extraction_HTML #####
#data-analytics-category
def extract_text_from_html(html_content, base_url):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remover tags indesejadas
    remove_tags = ["script", "style", "meta", "header", "footer", "nav", "aside",
                   "noscript", "img", "video", "audio", "canvas", "svg", "figure"]
    for tag in soup(remove_tags):
        tag.decompose()

    content_parts = []

    # Iterar por cada artigo
    for article in soup.find_all("article"):
        article_parts = []

        # --- Títulos e parágrafos ---
        for tag in article.find_all(["h1", "h2", "h3", "h4", "p"], recursive=True):
            if tag.name.startswith("h"):
                # Processar título com possível link
                content = ""
                for element in tag.descendants:
                    if element.name == "a" and element.get("href"):
                        link_text = element.get_text(strip=True)
                        if link_text:
                            link_href = urljoin(base_url, element["href"])
                            content += f"{link_text} ({link_href}) "
                    elif element.name is None and element.string:
                        content += element.string.strip() + " "
                
                # Se não encontrou links, pegar o texto simples
                if not content.strip():
                    content = tag.get_text(strip=True)
                
                content = re.sub(r'\s+', ' ', content.strip())
                if content:
                    level = tag.name[1]
                    article_parts.append(f"<h{level}>{content}</h{level}>")
                    
            else:  # parágrafos
                content = ""
                for element in tag.descendants:
                    if element.name == "a" and element.get("href"):
                        link_text = element.get_text(strip=True)
                        if link_text:
                            link_href = urljoin(base_url, element["href"])
                            content += f"{link_text} ({link_href}) "
                    elif element.name is None and element.string:
                        content += element.string.strip() + " "

                content = re.sub(r'\s+', ' ', content.strip())
                if content and len(content) > 10:
                    article_parts.append(f"<{tag.name}>{content}</{tag.name}>")

        # --- Data ---
        data = None
        time_tag = (article.find("time") or
                    article.find("span", class_="time") or
                    article.find("span", class_="datetime") or
                    article.find("span", class_="dateline"))
        if time_tag:
            data = time_tag.get_text(strip=True)
        if data:
            article_parts.append(f"<p><strong>Data:</strong> {data}</p>")

        # --- Autor ---
        autor = None
        # Público
        autor_tag = article.select_one("div.article__byline address.article__byline__author a")
        if autor_tag:
            autor = autor_tag.get_text(strip=True)
            autor_href = urljoin(base_url, autor_tag["href"])
            article_parts.append(f"<p><strong>Autor:</strong> {autor} ({autor_href})</p>")
        # Jornal de Negócios
        if not autor:
            autor_tag = article.select_one("a[data-analytics-category='Autor']")
            if autor_tag:
                autor = autor_tag.get_text(strip=True)
                autor_href = urljoin(base_url, autor_tag["href"])
                article_parts.append(f"<p><strong>Autor:</strong> {autor} ({autor_href})</p>")
        # --- Exclusividade ---
        exclusivo = False
        premium_tags = [
            ("span", {"class": "logo_premium"}),
            ("span", {"class": "exclusive-label"}),
            ("a", {"href": "/exclusivos"}),
            ("span", {"class": "ic_premium"}),
        ]

        # Verifica dentro do artigo
        for tag_name, attrs in premium_tags:
            if article.find(tag_name, attrs):
                exclusivo = True
                break

        # Adiciona ao conteúdo se for exclusivo
        if exclusivo:
            article_parts.append("<p><strong>Esta notícia é exclusiva para assinantes. O acesso pode ser limitado.</strong></p>")
        
        # Se o artigo tiver conteúdo válido, guardar
        if article_parts:
            content_parts.append("<article>\n" + "\n".join(article_parts) + "\n</article>")

    # --- Fallback: se não encontrar nenhum <article>, processar solto ---
    if not content_parts:
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "p"]):
            if tag.name.startswith("h"):
                # Processar título com possível link
                content = ""
                for element in tag.descendants:
                    if element.name == "a" and element.get("href"):
                        link_text = element.get_text(strip=True)
                        if link_text:
                            link_href = urljoin(base_url, element["href"])
                            content += f"{link_text} ({link_href}) "
                    elif element.name is None and element.string:
                        content += element.string.strip() + " "
                
                # Se não encontrou links, pegar o texto simples
                if not content.strip():
                    content = tag.get_text(strip=True)
                
                content = re.sub(r'\s+', ' ', content.strip())
                if content:
                    level = tag.name[1]
                    content_parts.append(f"<h{level}>{content}</h{level}>")
            else:
                content = ""
                for element in tag.descendants:
                    if element.name == "a" and element.get("href"):
                        link_text = element.get_text(strip=True)
                        if link_text:
                            link_href = urljoin(base_url, element["href"])
                            content += f"{link_text} ({link_href}) "
                    elif element.name is None and element.string:
                        content += element.string.strip() + " "
                content = re.sub(r'\s+', ' ', content.strip())
                if content and len(content) > 10:
                    content_parts.append(f"<{tag.name}>{content}</{tag.name}>")

    return "\n\n".join(content_parts)


def extract_categories_from_html(html_content, base_url):
    soup = BeautifulSoup(html_content, "html.parser")
    categories = []
    
    print("--> Entrei nas categorias melhoradas")
    li_tags = soup.find_all("li")
    
    for li_tag in li_tags:
        a_tag = li_tag.find("a", href=True)
        
        if not a_tag:
            continue
            
        text = a_tag.get_text(strip=True)
        href = a_tag["href"]
        
        #REVER
        if not text or len(text.split()) > 5:
            continue
            
        if any(x in href.lower() for x in ["#", "javascript:", "mailto:", "tel:"]):
            continue
            
        if href.startswith('http'):
            full_url = href
        else:
            full_url = urljoin(base_url, href)
        
        # Adicionar à lista se não for duplicado
        category_tuple = (text.strip(), full_url)
        if category_tuple not in categories:
            categories.append(category_tuple)
    
    # Remover duplicados baseados na URL (manter o primeiro título encontrado)
    unique_categories = []
    seen_urls = set()
    
    for title, url in categories:
        if url not in seen_urls:
            unique_categories.append((title, url))
            seen_urls.add(url)
    
    print(f"🔎 Categorias extraídas: {len(unique_categories)}")
    for title, url in unique_categories[:10]:
        print(f"   - {title}: {url}")
    
    return unique_categories

####################################################################

#### Double #####
DUPLICATE_THRESHOLD = 2

def load_tag_freq():
    """Carrega as frequências das tags do ficheiro JSON"""
    if os.path.exists(TAG_FREQ_FILE):
        with open(TAG_FREQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tag_freq(freq):
    """Guarda as frequências das tags no ficheiro JSON"""
    with open(TAG_FREQ_FILE, "w", encoding="utf-8") as f:
        json.dump(freq, f, indent=2)

def normalize_tag_content(content):
    """
    Normaliza o conteúdo de uma tag para gerar hash consistente
    """
    urls = sorted(set(re.findall(r'https?://\S+', content)))
    cleaned_content = re.sub(r'https?://\S+', '', content)
    cleaned_content = re.sub(r'[^\w\s]', '', cleaned_content)
    cleaned_content = re.sub(r'\s+', ' ', cleaned_content).strip().lower()
    
    return cleaned_content + " " + " ".join(urls)

def compute_tag_hash(tag_name, content):
    """Calcula hash para uma tag HTML específica"""
    normalized_content = normalize_tag_content(content)
    tag_string = f"{tag_name}:{normalized_content}"
    return hashlib.sha256(tag_string.encode("utf-8")).hexdigest()


####################################################################

#### ACTIONS #####

def scrape_link(retrieved_info, user_input, conv_vector_store, conversation_id, max_links=5):
    #print("\nA procura da notícia...")
    try:
        semantic_results = conv_vector_store.similarity_search(user_input, k=10)  # k ajustável
        semantic_links = []
        for doc in semantic_results:
            # Cada doc é um Document(page_content=..., metadata={...})
            url = doc.metadata.get("url")
            if url and url not in semantic_links:
                semantic_links.append(url)
        
        # Acrescentar esses links ao retrieved_info para a regex também os apanhar
        if semantic_links:
            retrieved_info += "\n\n" + "\n".join(
                [f"Relacionado: {url}" for url in semantic_links]
            )
    except Exception as e:
        print(f"[DEBUG] Erro na busca semântica no ChromaDB: {e}")
        
    matches = re.findall(r"([^\n()<>'\"]*?)[:\s]*[\(]?['\"]?(https?://[^\s>'\")]+)", retrieved_info)
    
    #for i, (text, url) in enumerate(matches):
    #    print(f"{i+1}. {text.strip()} — {url}")

    if not matches:
        print("Nenhum link encontrado.")
        return None
    
    # Monta a pergunta para o modelo
    #formatted_links = "\n".join([f"{i+1}. {text.strip()} — {url}" for i, (text, url) in enumerate(matches)])
    valid_urls = [url for _, url in matches]
    prompt = (
        f"O utilizador perguntou: \"{user_input}\"\n"
        f"Abaixo estão vários links com títulos ou descrições.\n"
        f"Seleciona até {max_links} links DIFERENTES que melhor respondem à pergunta. É muito importante que não seleciones links duplicados. \n"
        f"Enumera de 1 a {max_links} com os URLs exatos, um por linha. Não incluas texto explicativo:\n\n"
        f"{valid_urls}"
    )
    
    try:
        response = client.chat.completions.create(
            model = API_CONFIG["model"],
            messages = [
                {"role": "system", "content": system_prompt_informativo},
                {"role": "user", "content": prompt}
            ],
            temperature = API_CONFIG["temp"]
        )

        selected_urls_text = response.choices[0].message.content.strip()
        print(f"\nLinks encontrados pelo modelo:\n{selected_urls_text}")
        
        # Extrair URLs limpos
        selected_urls = []
        for line in selected_urls_text.split('\n'):
            match = re.search(r'(https?://\S+)', line)
            if match:
                selected_urls.append(match.group(1))
        
        #print(f"\nURLs limpos extraídos da resposta: {selected_urls}")
        
        if not selected_urls:
            print("Nenhum link válido encontrado na resposta.")
            return None
        
        # Verifica se os links estão entre os extraídos
        #valid_urls = [url for _, url in matches]
        #selected_urls = [url for url in selected_urls if url in valid_urls]
        selected_urls = [url.strip(")") for url in selected_urls]  # remove ) extra
        selected_urls = list(dict.fromkeys(selected_urls))
        
        if not selected_urls:
            print(f"AVISO: Nenhum dos links selecionados corresponde aos links extraídos.")
            return None
        
        all_scraped_content = []
        
        for selected_url in selected_urls:
            #print(f"[DEBUG] A tentar scrapear {selected_url}")
            try:
                response = requests.get(selected_url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    print(f"Página acessada com sucesso (HTTP {response.status_code})")
                    html_content = response.text
                    #print(f"Tamanho do HTML recebido: {len(html_content)} caracteres")
                    
                    # USAR A FUNÇÃO MELHORADA
                    scraped_content = extract_text_from_html(html_content, selected_url)
                    #print(f"Conteúdo extraído: {len(scraped_content)} caracteres")
                    
                    if not scraped_content or len(scraped_content) < 10:
                        print(f"AVISO: Conteúdo extraído muito pequeno ou vazio para {selected_url}!")
                        continue
                    
                    #print(f"\nSalvando conteúdo de {selected_url} no ChromaDB...")
                    try:
                        before_count = len(conv_vector_store.get()["ids"]) if conv_vector_store.get() else 0
                        # USAR A FUNÇÃO MELHORADA
                        save_to_chromadb(conv_vector_store, conversation_id, selected_url, scraped_content)
                        after_count = len(conv_vector_store.get()["ids"]) if conv_vector_store.get() else 0
                        
                        if after_count > before_count:
                            print(f"Conteúdo salvo com sucesso! (Documentos antes: {before_count}, depois: {after_count})")
                            # Adicionar URL e um resumo do conteúdo à lista de resultados
                            link_title = next((text for text, url in matches if url == selected_url), "Link")
                            all_scraped_content.append(f"Informações de '{link_title}':\n{scraped_content[:500]}...\n")
                        else:
                            print(f"AVISO: Parece que nenhum novo documento foi adicionado (antes: {before_count}, depois: {after_count})")
                    
                    except Exception as e:
                        print(f"Erro ao salvar no ChromaDB: {str(e)}")
                else:
                    print(f"Falha ao acessar o link ({response.status_code}): {selected_url}")
            
            except Exception as e:
                print(f"Erro ao acessar {selected_url}: {str(e)}")
                continue
        
        #print(f"[DEBUG] URLs finais selecionados: {selected_urls}")

        if all_scraped_content:
            return "\n\n".join(all_scraped_content)
        else:
            return "Não foi possível extrair conteúdo de nenhum dos links selecionados."
    
    except Exception as e:
        print(f"Erro ao selecionar ou scrapear links: {str(e)}")

    return None



def refresh_news_page(conv_vector_store, conversation_id):
    print("\nPedido de atualização de notícias detectado...")

    urls = get_current_urls(conversation_id)
    if not urls:
        print("Nenhum URL encontrado para esta conversa.")
        return None

    resultados = []

    for url in urls:
        print(f"A verificar: {url}")
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                resultados.append(f"- {url} Erro ao aceder (HTTP {response.status_code})")
                continue

            response.encoding = response.apparent_encoding
            html_content = response.text
            html_content = html_content.encode("utf-8").decode("utf-8", errors="ignore")

            scraped_content = extract_text_from_html(html_content, url)

            before_count = len(conv_vector_store.get()["ids"]) if conv_vector_store.get() else 0
            save_to_chromadb(conv_vector_store, conversation_id, url, scraped_content)
            after_count = len(conv_vector_store.get()["ids"]) if conv_vector_store.get() else 0

            novos_blocos = after_count - before_count
            if novos_blocos > 0:
                resultados.append(f"- {url} {novos_blocos} blocos novos encontrados")
            else:
                resultados.append(f"- {url} Nenhuma novidade encontrada")

        except Exception as e:
            print(f"Erro ao atualizar {url}: {str(e)}")
            resultados.append(f"- {url}  Erro ao aceder ({str(e)})")

    return "Resultado da verificação de novidades:\n\n" + "\n".join(resultados)


def resumir_com_gpt(user_input: str, retrieved_info: str, client, max_tokens=2500) -> str:
    """
    Usa GPT para resumir e filtrar os artigos do retrieved_info de acordo com o pedido do user.
    """
    system_prompt = (
        "Recebes excertos de notícias, cada um com um campo 'Order'.\n"
        "Esse campo indica a ordem de prioridade da página (Order=1 é a notícia mais destacada, "
        "depois Order=2, e assim sucessivamente).\n\n"
        "Tarefas:\n"
        "1. Se o utilizador pedir pela 'primeira notícia', 'segunda notícia', etc., "
        "usa SEMPRE o valor de 'Order' para responder, e não o conteúdo do texto.\n"
        "2. Mantém a ordem das notícias de acordo com o número 'Order'.\n"
        "3. Ignora conteúdo irrelevante.\n"
        "4. Responde em português claro, direto e organizado.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Pergunta do utilizador: {user_input}\n\nConteúdo encontrado:\n{retrieved_info}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # ou outro que uses
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3
    )

    return response.choices[0].message.content.strip()


def identify_relevant_link_from_previous(user_input, previous_links, ultima_resposta, client):
    """
    Identifica qual dos links anteriores é relevante para a nova pergunta do utilizador
    """
    if not previous_links or not ultima_resposta:
        return None
    
    # Se só há 1 link, retorna esse
    if len(previous_links) == 1:
        return previous_links[0]
    
    identification_prompt = f"""
A última resposta foi:
{ultima_resposta[:800]}

Links mencionados:
{chr(10).join([f"{i+1}. {link}" for i, link in enumerate(previous_links)])}

O utilizador agora pergunta: "{user_input}"

Qual destes links é o mais relevante para responder à nova pergunta?
Responde APENAS com o número do link (1, 2, 3, etc.) ou "NENHUM" se a pergunta não está relacionada com nenhum link anterior.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Identifica qual link anterior é relevante para a nova pergunta. Responde só com o número ou NENHUM."},
                {"role": "user", "content": identification_prompt}
            ],
            temperature=0
        )
        
        answer = response.choices[0].message.content.strip().upper()
        print(f"[DEBUG] Resposta do AI sobre link relevante: {answer}")
        
        if answer == "NENHUM":
            return None
        
        # Extrair número da resposta
        match = re.search(r'(\d+)', answer)
        if match:
            link_index = int(match.group(1)) - 1  # -1 porque lista começa em 0
            if 0 <= link_index < len(previous_links):
                selected_link = previous_links[link_index]
                print(f"[DEBUG] Link relevante identificado: {selected_link}")
                return selected_link
        
        return None
        
    except Exception as e:
        print(f"[DEBUG] Erro ao identificar link relevante: {e}")
        return None

def prepare_messages(user_input, conversation_history, conv_vector_store, conversation_id, intent_type=None, max_tokens=15000):
    encoding = tiktoken.get_encoding("cl100k_base")
    print(f"[DEBUG] prepare_messages chamada com intent: {intent_type}")
    messages = [{"role": "system", "content": system_prompt_informativo}]
    
    retrieved_info = ""
    previous_links = []
    ultima_resposta_completa = ""
    context_handled = False #Se o contexto foi tratado

    if conversation_history:
        last_assistant = next((m for m in reversed(conversation_history) if m["role"] == "assistant"), None)
        
        if last_assistant:
            previous_links = last_assistant.get("metadata", {}).get("links_utilizados", [])
            ultima_resposta_completa = last_assistant.get("metadata", {}).get("resposta_completa", "")
            
            if previous_links and ultima_resposta_completa:
                context_analysis_prompt = f"""
                    Última resposta do assistente:
                    {ultima_resposta_completa[:600]}

                    Links mencionados:
                    {chr(10).join([f"{i+1}. {link}" for i, link in enumerate(previous_links)])}

                    Nova pergunta do utilizador: "{user_input}"

                    Analisa e responde em JSON com este formato exato:
                    {{
                      "contexto": "CONTINUA" ou "NOVO_ASSUNTO",
                      "link_relevante": número do link (1, 2, 3...) ou null,
                      "razao": "breve explicação"
                    }}

                    Regras:
                    - "CONTINUA" = utilizador quer mais detalhes sobre algo já mencionado
                    - "NOVO_ASSUNTO" = pergunta completamente diferente
                    - link_relevante = qual link anterior é relevante (null se nenhum)
                    """
                
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Analisa o contexto da conversa e responde em JSON válido."},
                            {"role": "user", "content": context_analysis_prompt}
                        ],
                        temperature=0
                    )
                
                    analysis = json.loads(response.choices[0].message.content.strip())
                    
                    print(f"[DEBUG] Análise de contexto: {analysis}")
                    
                    # Resultado da decisão
                    if analysis["contexto"] == "NOVO_ASSUNTO":
                        print("[DEBUG] Novo assunto detectado - limpando links anteriores")
                        previous_links = []
                    
                    elif analysis["contexto"] == "CONTINUA" and analysis["link_relevante"]:
                        link_index = int(analysis["link_relevante"]) - 1
                        if 0 <= link_index < len(previous_links):
                            selected_link = previous_links[link_index]
                            print(f"[DEBUG] Link primário selecionado: {selected_link}")

                            # IDENTIFICAR LINKS RELACIONADOS
                            related_links = [selected_link] 

                            # Perguntar ao AI se há outros links relevantes sobre o mesmo tema
                            if len(previous_links) > 1:
                                multi_link_prompt = f"""
                                    A última resposta mencionou estas notícias:
                                    {chr(10).join([f"{i+1}. {link}" for i, link in enumerate(previous_links)])}
                
                                    O utilizador pediu: "{user_input}"
                                    O link principal identificado foi o nº {link_index + 1}.
                
                                    Existem OUTROS links desta lista que também são sobre o MESMO TEMA e que devem ser incluídos na resposta?
                                    (Ex: se há 3 notícias sobre o mesmo evento, inclui todas)
                
                                    Responde em JSON:
                                    {{
                                      "links_adicionais": [2, 3] ou [],
                                      "razao": "breve explicação"
                                    }}
                                    """
                                try:
                                    multi_response = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {"role": "system", "content": "Identifica links relacionados ao mesmo tema. Responde em JSON."},
                                            {"role": "user", "content": multi_link_prompt}
                                        ],
                                        temperature=0
                                    )

                                    multi_analysis = json.loads(multi_response.choices[0].message.content.strip())

                                    if multi_analysis.get("links_adicionais"):
                                        for idx in multi_analysis["links_adicionais"]:
                                            if 0 < idx <= len(previous_links) and idx != (link_index + 1):
                                                related_links.append(previous_links[idx - 1])

                                        print(f"[DEBUG] Links adicionais identificados: {multi_analysis['links_adicionais']}")
                                        print(f"[DEBUG] Razão: {multi_analysis['razao']}")

                                except Exception as e:
                                    print(f"[DEBUG] Erro ao identificar links adicionais: {e}")

                            previous_links = related_links
                            print(f"[DEBUG] Total de links a processar: {len(related_links)}")

                            # Processar os links relevantes
                            try:
                                all_documents = []
                                links_found = []
                                links_to_scrape = []

                                for link in related_links:
                                    # Normalizar URL
                                    parsed = urlparse(link)
                                    normalized_link = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '', ''))

                                    print(f"[DEBUG] Processando link: {link}")
                                    related_docs = None
                                    # Tentativa 1: primeiro_link
                                    related_docs = conv_vector_store._collection.get(
                                        where={"primeiro_link": link},
                                        include=["documents", "metadatas"]
                                    )
                                    # Tentativa 2: URL normalizado
                                    if not related_docs or not related_docs.get("documents"):
                                        related_docs = conv_vector_store._collection.get(
                                            where={"primeiro_link": normalized_link},
                                            include=["documents", "metadatas"]
                                        )

                                    # Tentativa 3: campo url
                                    if not related_docs or not related_docs.get("documents"):
                                        related_docs = conv_vector_store._collection.get(
                                            where={"url": link},
                                            include=["documents", "metadatas"]
                                        )

                                    # Tentativa 4: busca semântica
                                    if not related_docs or not related_docs.get("documents"):
                                        semantic_docs = conv_vector_store.similarity_search(link, k=2)
                                        if semantic_docs:
                                            related_docs = {
                                                "documents": [doc.page_content for doc in semantic_docs],
                                                "metadatas": [doc.metadata for doc in semantic_docs]
                                            }

                                    # Se encontrou, adicionar aos documentos
                                    if related_docs and related_docs.get("documents"):
                                        all_documents.extend(related_docs["documents"])
                                        links_found.append(link)
                                        print(f"[DEBUG] ✅ Conteúdo encontrado no ChromaDB para {link}")
                                    else:
                                        links_to_scrape.append(link)
                                        print(f"[DEBUG] ❌ Conteúdo não encontrado - vai precisar de scraping")

                                # 🆕 FAZER SCRAPING DOS LINKS QUE FALTAM
                                if links_to_scrape:
                                    print(f"[DEBUG] Iniciando scraping de {len(links_to_scrape)} links...")
                                    for link in links_to_scrape:
                                        try:
                                            response = requests.get(link, headers={"User-Agent": "Mozilla/5.0"})
                                            if response.status_code == 200:
                                                html_content = response.text
                                                scraped_content = extract_text_from_html(html_content, link)

                                                if scraped_content and len(scraped_content) > 50:
                                                    save_to_chromadb(conv_vector_store, conversation_id, link, scraped_content)
                                                    all_documents.append(scraped_content)
                                                    links_found.append(link)
                                                    print(f"[DEBUG] ✅ Scraping bem-sucedido: {link}")
                                                else:
                                                    print(f"[DEBUG] ⚠️ Conteúdo insuficiente em {link}")
                                            else:
                                                print(f"[DEBUG] ❌ Erro HTTP {response.status_code} para {link}")

                                        except Exception as scrape_error:
                                            print(f"[DEBUG] ❌ Erro ao scrapear {link}: {scrape_error}")

                                # Construir retrieved_info com todos os documentos
                                if all_documents:
                                    context_handled = True

                                    if len(links_found) == 1:
                                        retrieved_info = f"\n\nConteúdo sobre a notícia pedida ({links_found[0]}):\n"
                                    else:
                                        retrieved_info = f"\n\nConteúdo combinado de {len(links_found)} notícias relacionadas:\n"
                                        retrieved_info += "\n".join([f"- {link}" for link in links_found]) + "\n\n"

                                    retrieved_info += "\n\n".join(all_documents)

                                    print(f"[DEBUG] ✅ Total de {len(all_documents)} documentos recuperados")
                                    print(f"[DEBUG] Links processados: {links_found}")

                                else:
                                    print(f"[DEBUG] ❌ Nenhum conteúdo foi recuperado de nenhum link")

                            except Exception as e:
                                print(f"[DEBUG] Erro ao processar links múltiplos: {e}")
                                import traceback
                                traceback.print_exc()
                    
                except Exception as e:
                    print(f"[DEBUG] Erro na análise de contexto: {e}")
                    # Fallback: limpar links se houver erro
                    previous_links = []


    # --- Intent: request_more_info_cat ---
    if intent_type == "request_more_info_cat":
        retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)

        # Tentar identificar uma categoria correspondente
        try:
            category_docs = conv_vector_store._collection.get(
                where={"tipo": "categorias"}, include=["documents"]
            )
            category_text = category_docs["documents"][0] if category_docs["documents"] else ""
        except Exception as e:
            print(f"[DEBUG] Erro ao obter categorias: {e}")
            category_text = ""

        category_url = None
        for line in category_text.split("\n"):
            if ":" in line:
                cat_name, cat_link = line.split(":", 1)
                if cat_name.strip().lower() in user_input.lower() or user_input.lower() in cat_name.strip().lower():
                    category_url = cat_link.strip()
                    break

        if category_url:
            print(f"[DEBUG] Categoria encontrada: {category_url}")
            try:
                response = requests.get(category_url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    html = response.text
                    scraped = extract_text_from_html(html, category_url)
                    save_to_chromadb(conv_vector_store, conversation_id, category_url, scraped)
                    retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)
                    retrieved_info = (f"\n\n A informação abaixo foi extraída do separador '{cat_name.strip()}'." 
                                      + retrieved_info
                                      )
            except Exception as e:
                print(f"[DEBUG] Erro ao scrapear categoria: {e}")
        else:
            print("[DEBUG] Nenhuma categoria encontrada — tentando scraping por links\n\n")
            scraped_content = scrape_link(retrieved_info, user_input, conv_vector_store, conversation_id, max_links=5)
            if scraped_content:
                retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)
                retrieved_info = (
                    "\n\nInforma SEMPRE QUE Não encontras-te a categoria que o user pediu,"
                    "mas conseguis-te arranjar artigos relacionados com o tema pedido. "
                    "Deves SEMPRE usar a esta informação para responder ao utilizador." 
                    + retrieved_info
                )
            else:
                retrieved_info = (
                    "\n\nNão encontrei a secção que procura\n' "
                    "e também não encontrei artigos relacionados com esse tema."
                    + retrieved_info
                )

    #Só faz scraping se não nada relacionado
    # --- Intent: request_more_info_not ---
    elif intent_type == "request_more_info_not":
        if not context_handled:
            print("[DEBUG] Contexto não resolvido - fazendo scraping genérico")
            scraped_content = scrape_link(retrieved_info, user_input, conv_vector_store, conversation_id, max_links=3)
            if scraped_content:
                retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)
                retrieved_info = "\n\nInformação encontrada através de scraping:\n" + retrieved_info
        else:
            print("[DEBUG] Contexto já resolvido - usando informação anterior")
        
    # --- Intent: refresh ---
    elif intent_type == "refresh":
        retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)
        print("[DEBUG] Intent é REFRESH - fazendo refresh da página")
        refreshed = refresh_news_page(conv_vector_store, conversation_id)
        if refreshed:
            retrieved_info += "\n\n🆕 Novas informações extraídas da página atual:\n" + refreshed
    
    # --- Intent: ask_highlight ---
    elif intent_type == "ask_highlight":
        print("ENTREI NO ASK_HIGHLIGHT")
        retrieved_info = retrieve_from_chromadb_by_order(conv_vector_store, top_n=10)
    
    # --- Intent: ask_question and unknown ---
    elif intent_type in ["ask_question", "unknown"]:
        print("ENTREI NO ASK_QUESTION")
        retrieved_info = retrieve_from_chromadb(user_input, conv_vector_store)

    ## --- Escolher o system prompt adequado ---
    #if intent_type == "help":
    #    system_prompt_custom = (
    #        "Explica de forma simples e clara como o assistente funciona. "
    #        "Evita termos técnicos e usa linguagem acessível, como se estivesses a falar com alguém sem experiência em tecnologia. "
    #        "Usa exemplos fáceis de entender sempre que possível. "
    #    )
    #    messages = [{"role": "system", "content": system_prompt_custom}]
    #else:
    #    messages = [{"role": "system", "content": system_prompt_informativo}]

    # 🆕 CORRIGIDO: Só resume se temos conteúdo
    if retrieved_info:
        print(f"Informação antes de resumir: {retrieved_info[:500]}...")
        retrieved_info = resumir_com_gpt(user_input, retrieved_info, client, max_tokens=2500)
        print("[DEBUG] Contexto RAG truncado para 2500 tokens")

    # Adiciona a resposta anterior
    if intent_type in ["request_more_info_cat", "request_more_info_not", "ask_question", "ask_highlight", "refresh", "unknown"]: #"help"
        last_msgs = [msg for msg in conversation_history if msg["role"] == "assistant"][-2:]
        if last_msgs:
            resumo_contexto = "As últimas respostas foram:\n"
            for m in last_msgs:
                resumo_contexto += f"- {m['parts'][0][:300]}...\n"
            retrieved_info += "\n\nNota: Evita repetir está informação que já foi dada antes.\n" + resumo_contexto
    
    print(f"Conteudo extraido final: {retrieved_info[:500]}...")
    
    # Adiciona a última mensg  
    messages.extend([
        {"role": msg["role"], "content": msg["parts"][0]} for msg in conversation_history[-2:]
    ])

    ## Construir o full_input com base no intent
    #if intent_type == "help":
    #    full_input = user_input
    #else:
    full_input = f"Contexto relevante:\n{retrieved_info}\n\nInput: {user_input}" if retrieved_info else user_input

    messages.append({"role": "user", "content": full_input})
    
    # Verifica o limite de tokens
    total_tokens = sum(len(encoding.encode(m["content"])) for m in messages)
    if total_tokens > max_tokens:
        print(f"⚠️ Excesso de tokens ({total_tokens}) — enviando apenas pergunta")
        messages = [{"role": "system", "content":system_prompt_informativo}]
        messages.append({"role": "user", "content": user_input})

    print(f"[DEBUG] Mensagens preparadas: {len(messages)} mensagens (~{total_tokens} tokens)")
    print(f"[DEBUG] Links finais a propagar: {previous_links}")
    
    return messages, conversation_history



####################################################################

#### STT #####
ALLOWED_AUDIO_EXTENSIONS = {'webm'} #'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'wav', 'webm'
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB (limite do Whisper)

def allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

####################################################################
def extract_requested_news_index(user_input: str) -> int | None:
    # regex para apanhar "2ª", "2a", "segunda", etc.
    match = re.search(r'(\d+)[ªa]?\s*notícia', user_input, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def gerar_resposta_conversacional(resposta_completa, user_input):
    print(f"Resposta complçeta {resposta_completa}")
    try:
        response = client.chat.completions.create(
            model=API_CONFIG["model"],
            messages=[
                {"role": "system", "content": system_prompt_conversacional},
                {"role": "user", "content": (
                    f"O utilizador pediu: '{user_input}'.\n\n"
                    f"A resposta original foi:\n---\n{resposta_completa}\n---\n\n"
                    f"Reescreve esta resposta seguindo as instruções do system_prompt."
                )}
            ],
            temperature=API_CONFIG["temp"]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERRO] Conversão para estilo conversacional: {e}")
        return resposta_completa 

  
#### Mensagem processada #####
def process_message(user_input, conversation_id):
    model_response, metadata = dialog_manager.process_input(user_input)

    action = metadata.get("action")
    needs_rag = metadata.get("needs_rag", False)
    intent = metadata.get("intent")

    print(f"[DEBUG] Acção definida: {action}")
    print(f"[DEBUG] Intent: {intent}")
    print(f"[DEBUG] Needs RAG: {needs_rag}")

    if not metadata.get("requires_action", False):
        print(f"[DEBUG] Não requer acção - retornando resposta direta")
        return {
            'transcribed_text': user_input,
            'response': model_response,
            'conversation_id': conversation_id,
            'metadata': metadata
        }

    vector_store = get_conversation_vector_store(conversation_id)
    conversation_history = (
        load_conversation(conversation_id + ".json")
        if os.path.exists(os.path.join(HISTORY_FOLDER, conversation_id + ".json"))
        else []
    )

    is_first_message = len(conversation_history) == 0

    if needs_rag:
        messages, conversation_history = prepare_messages(
            user_input,
            conversation_history,
            vector_store,
            conversation_id,
            intent_type=intent
        )

        print(f"[DEBUG] Mensagens preparadas para envio ao modelo.")
        
        response = client.chat.completions.create(
            model=API_CONFIG["model"],
            messages=messages,
            temperature=API_CONFIG["temp"]
        )

        raw_model_text = response.choices[0].message.content
        print(f"[DEBUG] Conteúdo bruto: {raw_model_text[:300]}...")

        model_response = make_links_clickable(raw_model_text)
        final_response = gerar_resposta_conversacional(model_response, user_input)


        if is_first_message:
            generate_conversation_title(model_response, conversation_id)

    # Guardar no histórico COM metadata do link
    conversation_history.append({"role": "user", "parts": [user_input]})
    
    assistant_metadata = {"resposta_completa": model_response}
    
    links_utilizados = re.findall(r'href="(https?://[^"]+)"', model_response)
    links_utilizados = list(set(links_utilizados))  # remove duplicados
    print(f"[DEBUG] Links extraídos da resposta: {links_utilizados}")
    if not links_utilizados:
        if conversation_history:
            for msg in reversed(conversation_history):
                if msg["role"] == "assistant" and "metadata" in msg:
                    previous_links = msg["metadata"].get("links_utilizados")
                    if previous_links:
                        links_utilizados = previous_links
                        print(f"[DEBUG] Nenhum link novo — a reutilizar anterior: {links_utilizados}")
                        break
    assistant_metadata["links_utilizados"] = links_utilizados  # guarda todos os links usados
    

    
    conversation_history.append({
        "role": "assistant",
        "parts": [final_response],
        "metadata": assistant_metadata
    })

    
    save_conversation(conversation_history, conversation_id + ".json")

    print(f"[DEBUG] Resposta completa armazenada ({len(model_response)} chars)")


    return {
        'transcribed_text': user_input,
        'response': final_response,
        'conversation_history': conversation_history,
        'conversation_id': conversation_id,
        'conversation_title': get_conversation_title(conversation_id),
        'metadata': {**metadata, 'links_utilizados': links_utilizados},
        'debug_info': {
            'intent': intent,
            'action': action,
            'needs_rag': needs_rag,
            'link_usado': links_utilizados
        }
    }








'''---------------------------------------------------'''


app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["chrome-extension://*", "http://localhost:5000", "http://127.0.0.1:5000"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
}) 

@app.after_request
def after_request(response):
    """Adiciona headers CORS manualmente (fallback)"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.before_request
def log_request_info():
    """Log de todas as requisições para debug"""
    print(f"📥 {request.method} {request.url}")
    if request.method == "POST":
        print(f"   Body: {request.get_data(as_text=True)[:200]}")

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'message': 'Servidor Blinkin a funcionar',
        'endpoints': {
            'scrape': '/scrape [POST]',
            'send_message': '/send_message [POST]',
            'conversations': '/conversations [GET]',
            'conversation': '/conversation/<id> [GET, DELETE]',
            'STT': '/STT [POST]',
            'clear_block_freq': '/clear_block_freq [POST]'
        }
    })

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        data = request.get_json()
        url = data.get("url")
        print(f"📍 URL recebido: {url}")
        
        if not url:
            return jsonify({"error": "URL não fornecida"}), 400

        conversation_id = data.get("conversation_id")
        if not conversation_id:
            conversation_id = generate_conversation_id()
        
        print(f"🆔 Conversation ID: {conversation_id}")
        
        print("🌐 A fazer pedido HTTP...")
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"error": f"Erro ao acessar URL: {response.status_code}"}), response.status_code
        
        print("✅ Página carregada com sucesso")
        
        response.encoding = response.apparent_encoding
        html_content = response.text
        html_content = html_content.encode("utf-8").decode("utf-8", errors="ignore")
        
        print(f"📄 HTML recebido: {len(html_content)} caracteres")
        
        print("🔍 A extrair categorias...")
        categories = extract_categories_from_html(html_content, url)
        print(f"✅ {len(categories)} categorias extraídas")
        
        print("📝 A extrair texto...")
        extracted_text = extract_text_from_html(html_content, url)
        print(f"✅ Texto extraído: {len(extracted_text)} caracteres")
        
        print("🗄️ A criar/carregar vector store...")
        vector_store = get_conversation_vector_store(conversation_id)
        print("✅ Vector store pronto")
        
        print("💾 A guardar no ChromaDB...")
        
        # 🔧 ADICIONAR TRY-CATCH ESPECÍFICO AQUI
        try:
            success = save_to_chromadb(vector_store, conversation_id, url, extracted_text, categories)
            
            if success:
                print("✅ Dados guardados com sucesso!")
                return jsonify({
                    "message": "Página processada e armazenada no RAG",
                    "conversation_id": conversation_id,
                    "categories_found": len(categories),
                    "debug_categories": categories[:5]
                })
            else:
                print("⚠️ Falha ao guardar no ChromaDB")
                return jsonify({"error": "Falha ao guardar dados"}), 500
                
        except Exception as db_error:
            print(f"❌ ERRO NO CHROMADB: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Erro no ChromaDB: {str(db_error)}"}), 500
        
    except requests.Timeout:
        print("⏱️ Timeout ao aceder à página")
        return jsonify({"error": "Timeout ao aceder à página"}), 504
    
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro: {str(e)}"}), 500
    


@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    user_input = data.get('user_input', '')
    conversation_id = data.get("conversation_id")

    if not user_input or not conversation_id:
        return jsonify({'error': 'Falta o input ou conversation_id.'}), 400

    print(f"[DEBUG] Input recebido: '{user_input}'")
    print(f"[DEBUG] Conversation ID: {conversation_id}")

    result = process_message(user_input, conversation_id)
    return jsonify(result)


@app.route('/conversations', methods=['GET'])
def list_conversations_with_titles():
    """Lista todas as conversas com os seus títulos"""
    try:
        conversations = get_all_conversations_with_titles()
        return jsonify({'conversations': conversations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

###############################################################

@app.route('/conversation/<conversation_id>', methods=['DELETE'])
def delete_conversation_api(conversation_id):
    try:
        clean_id = conversation_id.replace('.json', '')
        
        # Apagar ficheiro de conversa
        conv_file = os.path.join(HISTORY_FOLDER, f"{clean_id}.json")
        if os.path.exists(conv_file):
            os.remove(conv_file)
        
        # Remover título
        titles = load_conversation_titles()
        if clean_id in titles:
            del titles[clean_id]
            save_conversation_titles(titles)
        
        return jsonify({'message': 'Conversa apagada com sucesso'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
###############################################################

@app.route('/conversation/<conversation_id>', methods=['GET'])
def load_conversation_api(conversation_id):
    try:
        # Remove .json se vier no ID
        clean_id = conversation_id.replace('.json', '')
        
        conv = load_conversation(f"{clean_id}.json")
        vector_store = get_conversation_vector_store(clean_id)
        docs = vector_store.get(include=["documents", "metadatas"])
        retrieved_info = "\n\n".join(docs["documents"]) if docs.get("documents") else ""
        
        # Incluir título na resposta
        title = get_conversation_title(clean_id)
        
        return jsonify({
            'conversation': conv,
            'retrieved_info': retrieved_info,
            'conversation_id': clean_id,
            'title': title  # NOVO
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear_block_freq', methods=['POST'])
def clear_tag_frequencies():
    """Limpa o ficheiro de frequências das tags"""
    try:
        with open(TAG_FREQ_FILE, 'w') as f:
            f.write("{}")
        return jsonify({'message': 'Frequências das tags limpas com sucesso'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/STT', methods=['POST'])
def STT():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'Nenhum ficheiro de áudio enviado'}), 400
        
        audio_file = request.files['audio']
        conversation_id = request.form.get('conversation_id', '')
        language = request.form.get('language', 'pt')
        
        if not conversation_id:
            return jsonify({'error': 'conversation_id é obrigatório'}), 400
        
        if audio_file.filename == '' or not allowed_audio_file(audio_file.filename):
            return jsonify({'error': 'Ficheiro de áudio inválido'}), 400
        
        audio_file.seek(0, os.SEEK_END)
        file_size = audio_file.tell()
        audio_file.seek(0)
        
        if file_size > MAX_AUDIO_SIZE:
            return jsonify({'error': 'Ficheiro muito grande (máximo 25MB)'}), 400
        
        # Guardar áudio temporariamente
        temp_fd, temp_path = tempfile.mkstemp(suffix=".input")
        os.close(temp_fd)
        audio_file.save(temp_path)

        # Converter áudio para WAV compatível com silero (PCM 16-bit, mono)
        converted_path = temp_path + "_converted.wav"
        try:
            sound = AudioSegment.from_file(temp_path)
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)  # mono, 16kHz, 16-bit PCM
            sound.export(converted_path, format="wav")
        except Exception as e:
            os.remove(temp_path)
            return jsonify({'error': f'Erro ao converter áudio: {e}'}), 500

        # VAD com silero
        try:
            vad_model = load_silero_vad()
            audio = read_audio(converted_path)
            speech_timestamps = get_speech_timestamps(audio, vad_model, return_seconds=True)

            if not speech_timestamps:
                os.remove(temp_path)
                os.remove(converted_path)
                return jsonify({'error': 'Nenhuma fala detetada no áudio'}), 400
        except Exception as e:
            os.remove(temp_path)
            os.remove(converted_path)
            return jsonify({'error': f'Erro ao processar VAD: {e}'}), 500

        # Transcrever com Whisper
        try:
            with open(converted_path, 'rb') as audio_data:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_data,
                    language=language,
                    response_format="text"
                )
        except Exception as e:
            os.remove(temp_path)
            os.remove(converted_path)
            return jsonify({'error': f'Erro no Whisper: {e}'}), 500

        user_input = transcript.strip()
        os.remove(temp_path)
        os.remove(converted_path)

        if not user_input:
            return jsonify({'error': 'Nenhum texto foi detetado no áudio'}), 400

        print(f"[SPEECH] Texto transcrito: '{user_input}'")

        result = process_message(user_input, conversation_id)
        return jsonify(result)

    except Exception as e:
        print(f"Erro geral no STT: {str(e)}")
        return jsonify({'error': str(e)}), 500