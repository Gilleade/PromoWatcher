import os
import time
import re
import smtplib
import ssl
import hashlib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from unidecode import unidecode

load_dotenv()

NOTIFY_CHAT = os.getenv("NOTIFY_CHAT", "").strip() or "me"  # '@ALERTAS_PROMO' ou id numérico; fallback 'me'
NOTIFY_DEST = NOTIFY_CHAT  # será substituído por entidade resolvida

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
CHATS_RAW = os.getenv("TELEGRAM_CHATS", "").strip()
MONITORED_CHATS = [c.strip() for c in CHATS_RAW.split(",") if c.strip()]
KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.txt")
CASE_INSENSITIVE = os.getenv("CASE_INSENSITIVE", "true").lower() == "true"
ACCENT_INSENSITIVE = os.getenv("ACCENT_INSENSITIVE", "true").lower() == "true"
NORMALIZE_SPACES_DASHES = os.getenv("NORMALIZE_SPACES_DASHES", "true").lower() == "true"

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "45"))
DEDUP_WINDOW = int(os.getenv("DEDUP_WINDOW", "3600"))
SILENT_HOURS = os.getenv("SILENT_HOURS", "").strip()

SEND_TO_TELEGRAM = os.getenv("SEND_TO_TELEGRAM", "true").lower() == "true"
FORWARD_OR_COPY = os.getenv("FORWARD_OR_COPY", "forward").lower()

SEND_EMAIL = os.getenv("SEND_EMAIL", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "[Promoções] Alerta de palavra-chave")

SESSION_NAME = "tg_promos_session"
KEYWORDS_POLL_INTERVAL = 30  # segundos entre verificações do arquivo
last_keywords_mtime = 0
compiled_patterns = []

# Anti-spam/duplicados
last_sent_ts = {}   # key: hash -> timestamp

def parse_silent_hours():
    # Formato "23-07" -> range 23..24 e 0..7
    if not SILENT_HOURS:
        return None
    try:
        s, e = SILENT_HOURS.split("-")
        start = int(s)
        end = int(e)
        return (start, end)
    except:
        return None

def is_silent_now():
    rng = parse_silent_hours()
    if not rng:
        return False
    start, end = rng
    now_h = datetime.now().hour
    if start <= end:
        return start <= now_h <= end
    # faixa atravessa meia-noite
    return (now_h >= start) or (now_h <= end)

def normalize_text(s: str) -> str:
    t = s
    if ACCENT_INSENSITIVE:
        t = unidecode(t)
    if NORMALIZE_SPACES_DASHES:
        t = t.replace("-", " ")
        t = re.sub(r"\s+", " ", t)
    if CASE_INSENSITIVE:
        t = t.lower()
    return t

def load_keywords():
    """(Re)carrega keywords do arquivo quando o mtime muda, criando regex tolerantes."""
    global last_keywords_mtime, compiled_patterns
    try:
        mtime = os.path.getmtime(KEYWORDS_FILE)
    except FileNotFoundError:
        compiled_patterns = []
        print(f"[keywords] arquivo {KEYWORDS_FILE} não encontrado — 0 carregadas")
        return
    if mtime == last_keywords_mtime:
        return
    last_keywords_mtime = mtime

    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        raw = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

    patterns = []
    for kw in raw:
        n = normalize_text(kw)
        # quebra em palavras
        parts = n.split()
        # junta permitindo variações de espaço, hífen ou nada entre as partes
        regex_str = r"[\s\-]*".join(map(re.escape, parts))
        # para plural opcional (ex.: louca -> loucas)
        if regex_str.endswith("a"):
            regex_str = regex_str + "s?"
        pat = re.compile(regex_str, re.IGNORECASE if CASE_INSENSITIVE else 0)
        patterns.append(pat)

    compiled_patterns = patterns
    print(f"[keywords] {len(compiled_patterns)} carregadas de {KEYWORDS_FILE}")

def match_keywords(text: str) -> bool:
    if not compiled_patterns:
        return False
    norm = normalize_text(text)
    for pat in compiled_patterns:
        if pat.search(norm):
            return True
    return False

def dedup_key(chat_id: int, msg_id: int, text: str) -> str:
    base = f"{chat_id}:{msg_id}:{normalize_text(text)[:200]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def should_send(dkey: str) -> bool:
    # cooldown/duplicados
    now = time.time()
    # limpa antigos
    for k, ts in list(last_sent_ts.items()):
        if now - ts > DEDUP_WINDOW:
            del last_sent_ts[k]
    last_ts = last_sent_ts.get(dkey)
    if last_ts and (now - last_ts < COOLDOWN_SECONDS):
        return False
    last_sent_ts[dkey] = now
    return True

def send_email(subject: str, body: str):
    if not SEND_EMAIL:
        return
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and EMAIL_TO):
        print("[email] Config SMTP incompleta — pulando.")
        return
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
    print("[email] Enviado.")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

@client.on(events.NewMessage(chats=MONITORED_CHATS if MONITORED_CHATS else None))
async def handler(event):
    try:
        # recarrega keywords periodicamente
        load_keywords()

        # ignora se janela silenciosa
        if is_silent_now():
            return

        m = event.message
        text = m.message or ""
        # também considera legenda de mídia
        if not text and getattr(m, "raw_text", ""):
            text = m.raw_text

        if not text:
            return

        if not match_keywords(text):
            return

        chat = await event.get_chat()
        chat_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(chat.id)

        dkey = dedup_key(chat.id, m.id, text)
        if not should_send(dkey):
            return

        # Telegram delivery
        if SEND_TO_TELEGRAM:
            if FORWARD_OR_COPY == "forward":
                #await m.forward_to("me")  # encaminha original (mantém mídia/links)
                await m.forward_to(NOTIFY_DEST)  # encaminha original (mantém mídia/links)
                print(f"[tg] Encaminhado de {chat_name}")
            else:
                header = f"Alerta ({chat_name}):\n"
                #await client.send_message("me", header + text)
                await client.send_message(NOTIFY_DEST, header + text, silent=False)
                print(f"[tg] Copiado de {chat_name}")

        # Email delivery
        if SEND_EMAIL:
            link_hint = ""
            try:
                # Tenta gerar um link t.me se o chat tiver username público
                uname = getattr(chat, "username", None)
                if uname:
                    link_hint = f"\n\nPossível link: https://t.me/{uname}/{m.id}"
            except:
                pass

            body = f"Chat: {chat_name}\nMensagem:\n{text}{link_hint}"
            send_email(EMAIL_SUBJECT, body)

    except Exception as e:
        print(f"[handler] erro: {e}")

async def resolve_notify_dest():
    """Resolve NOTIFY_CHAT para uma entidade Telethon (canal/usuário) ou 'me'."""
    global NOTIFY_DEST
    try:
        if NOTIFY_CHAT == "me":
            NOTIFY_DEST = "me"
            print("[notify] destino = Mensagens Salvas")
            return
        entity = await client.get_entity(NOTIFY_CHAT)
        NOTIFY_DEST = entity
        title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(getattr(entity, "id", NOTIFY_CHAT))
        print(f"[notify] destino = {title}")
    except Exception as e:
        print(f"[notify] falha ao resolver '{NOTIFY_CHAT}': {e} — usando 'me'")
        NOTIFY_DEST = "me"

@client.on(events.MessageEdited(chats=MONITORED_CHATS if MONITORED_CHATS else None))
async def handler_edited(event):
    # Reaproveita sua lógica principal
    await handler(event)

def main():
    if not API_ID or not API_HASH:
        raise RuntimeError("Configure TELEGRAM_API_ID e TELEGRAM_API_HASH no .env")
    print("Iniciando monitor de promoções (Telegram)…")
    if MONITORED_CHATS:
        print("Monitorando chats específicos:", ", ".join(MONITORED_CHATS))
    else:
        print("Monitorando TODOS os chats/canais que sua conta acessa.")
    load_keywords()
    client.start()  # login/2FA na primeira vez
    client.loop.run_until_complete(resolve_notify_dest())
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
