import asyncio
import os
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.mime.text import MIMEText

from telethon import events

from app.config import get_config
from app.database import get_connection, init_db, insert_notification
from app.products.enrichment_worker import enrichment_worker_loop
from app.rules.alert_matcher import load_alerts, sync_alerts_to_db
from app.services.message_processor import process
from app.services.notification_service import build_notification_text
from app.telegram_client import create_client

config = get_config()

NOTIFY_CHAT = config.notify_chat
NOTIFY_DEST = NOTIFY_CHAT  # será substituído por entidade resolvida

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

ALERTS_POLL_INTERVAL = 30  # segundos entre verificações do arquivo alerts.json
_last_alerts_mtime = 0
_alerts_cache: list = []

executor = ThreadPoolExecutor(max_workers=4)


def parse_silent_hours():
    # Formato "23-07" -> range 23..24 e 0..7
    if not SILENT_HOURS:
        return None
    try:
        s, e = SILENT_HOURS.split("-")
        return int(s), int(e)
    except Exception:
        return None


def is_silent_now():
    rng = parse_silent_hours()
    if not rng:
        return False
    start, end = rng
    now_h = datetime.now().hour
    if start <= end:
        return start <= now_h <= end
    return (now_h >= start) or (now_h <= end)


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


def reload_alerts_if_needed(conn):
    """(Re)carrega alerts.json quando o mtime muda, sincronizando com a tabela alerts."""
    global _last_alerts_mtime, _alerts_cache
    try:
        mtime = os.path.getmtime(config.alerts_file)
    except FileNotFoundError:
        _alerts_cache = []
        print(f"[alerts] arquivo {config.alerts_file} não encontrado — 0 carregados")
        return _alerts_cache
    if mtime == _last_alerts_mtime:
        return _alerts_cache

    _last_alerts_mtime = mtime
    alerts = load_alerts(config.alerts_file)
    alerts = sync_alerts_to_db(conn, alerts)
    _alerts_cache = alerts
    print(f"[alerts] {len(_alerts_cache)} carregados de {config.alerts_file}")
    return _alerts_cache


def _process_in_worker_thread(telegram_message_id, chat_id, chat_title, sender_id,
                               text, message_date, alerts, has_media=False,
                               local_image_path=None):
    """Roda o pipeline em uma conexão SQLite própria da worker thread — uma
    Connection do sqlite3 não pode ser compartilhada entre threads."""
    conn = get_connection(config.db_path)
    try:
        return process(
            conn,
            telegram_message_id=telegram_message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            sender_id=sender_id,
            message_text=text,
            message_date=message_date,
            alerts=alerts,
            has_media=has_media,
            local_image_path=local_image_path,
            accent_insensitive=config.accent_insensitive,
            normalize_spaces_dashes=config.normalize_spaces_dashes,
            case_insensitive=config.case_insensitive,
            link_resolve_timeout=config.link_resolve_timeout,
        )
    finally:
        conn.close()


client = create_client(config)
db_conn = init_db(config.db_path)


async def _download_message_photo(m, chat_id: int):
    """Baixa a foto anexada à mensagem (quando houver) para IMAGES_DIR, com
    nome determinístico e rastreável à mensagem de origem. Nunca lança:
    qualquer falha (timeout, sem permissão de escrita, mídia expirada etc.)
    só loga e retorna None — a promoção segue seu caminho normal sem
    imagem, mesma filosofia do resolve_links() para links quebrados (nunca
    descarta a promoção por causa de uma falha auxiliar)."""
    photo = getattr(m, "photo", None)
    if photo is None:
        return None
    try:
        os.makedirs(config.images_dir, exist_ok=True)
        filename = f"{chat_id}_{m.id}_{photo.id}.jpg"
        path = os.path.join(config.images_dir, filename)
        if os.path.exists(path):
            return path
        return await asyncio.wait_for(
            client.download_media(m, file=path),
            timeout=config.media_download_timeout,
        )
    except Exception as e:
        print(f"[media] falha ao baixar foto da msg {m.id}: {type(e).__name__}: {e}")
        return None


@client.on(events.NewMessage(chats=config.telegram_chats if config.telegram_chats else None))
async def handler(event):
    try:
        alerts = reload_alerts_if_needed(db_conn)

        if is_silent_now():
            return

        m = event.message
        text = m.message or ""
        if not text and getattr(m, "raw_text", ""):
            text = m.raw_text
        if not text:
            return

        chat = await event.get_chat()
        chat_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(chat.id)
        message_date = m.date.isoformat() if m.date else datetime.utcnow().isoformat()

        local_image_path = await _download_message_photo(m, chat.id)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _process_in_worker_thread,
                                             m.id, chat.id, chat_name,
                                             getattr(m, "sender_id", None), text,
                                             message_date, alerts, bool(m.media),
                                             local_image_path)

        if not result.notify:
            print(f"[pipeline] {result.status} de {chat_name}: {result.reason}")
            return

        notification_text = build_notification_text(
            alert=result.matched_alert,
            alert_name=result.product_alert_name,
            title_guess=result.parsed.title_guess,
            price=float(result.parsed.price) if result.parsed.price is not None else None,
            coupon=result.parsed.coupon,
            installment_count=result.parsed.installment_count,
            installment_price=float(result.parsed.installment_price)
            if result.parsed.installment_price is not None else None,
            installment_no_interest=result.parsed.installment_no_interest,
            link_status=result.link_result.status.value,
            url=result.link_result.url or None,
            source_chat_title=chat_name,
            score=result.score,
            repeat_count=result.repeat_count or 0,
            reason=result.reason,
        )

        if SEND_TO_TELEGRAM:
            try:
                await client.send_message(NOTIFY_DEST, notification_text, silent=False)
                if FORWARD_OR_COPY == "forward":
                    await m.forward_to(NOTIFY_DEST)
                insert_notification(
                    db_conn,
                    promotion_id=result.promotion_id,
                    alert_id=result.matched_alert.id if result.matched_alert else None,
                    product_alert_id=result.product_alert_id,
                    channel="telegram",
                    message_sent=notification_text,
                    status="SENT",
                )
                print(f"[tg] Notificado de {chat_name} (score={result.score})")
            except Exception as e:
                insert_notification(
                    db_conn,
                    promotion_id=result.promotion_id,
                    alert_id=result.matched_alert.id if result.matched_alert else None,
                    product_alert_id=result.product_alert_id,
                    channel="telegram",
                    message_sent=notification_text,
                    status="ERROR",
                    error_message=str(e),
                )
                print(f"[tg] erro ao notificar: {e}")

        if SEND_EMAIL:
            send_email(EMAIL_SUBJECT, notification_text)

    except Exception as e:
        print(f"[handler] erro: {e}")


async def resolve_notify_dest():
    """Resolve NOTIFY_CHAT para uma entidade Telethon (canal/usuário) ou 'me'.
    Nunca loga o valor de NOTIFY_CHAT nem o identificador resolvido (dado sensível)."""
    global NOTIFY_DEST
    try:
        if NOTIFY_CHAT == "me":
            NOTIFY_DEST = "me"
            print("[notify] destino resolvido com sucesso.")
            return
        entity = await client.get_entity(NOTIFY_CHAT)
        NOTIFY_DEST = entity
        print("[notify] destino resolvido com sucesso.")
    except Exception as e:
        print(f"[notify] falha ao resolver destino configurado — usando 'me'. Detalhe: {type(e).__name__}")
        NOTIFY_DEST = "me"


@client.on(events.MessageEdited(chats=config.telegram_chats if config.telegram_chats else None))
async def handler_edited(event):
    # Reaproveita a lógica principal
    await handler(event)


def main():
    if not config.telegram_api_id or not config.telegram_api_hash:
        raise RuntimeError("Configure TELEGRAM_API_ID e TELEGRAM_API_HASH no .env")
    print("Iniciando monitor de promoções (Telegram) — pipeline MVP1…")
    if config.telegram_chats:
        print("Monitorando chats específicos:", ", ".join(config.telegram_chats))
    else:
        print("Monitorando TODOS os chats/canais que sua conta acessa.")
    reload_alerts_if_needed(db_conn)
    client.start()  # login/2FA na primeira vez
    client.loop.run_until_complete(resolve_notify_dest())
    client.loop.create_task(
        enrichment_worker_loop(lambda: get_connection(config.db_path), config)
    )
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
