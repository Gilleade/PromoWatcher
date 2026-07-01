from datetime import datetime, timedelta

import streamlit as st

from app.config import get_config
from app.database import get_connection
from app.services.promotion_service import (
    dashboard_counts,
    list_alerts,
    list_promotions,
    list_raw_messages,
)


@st.cache_resource
def _get_conn():
    config = get_config()
    conn = get_connection(config.db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _since_today() -> str:
    # created_at é gravado via SQLite datetime('now') em UTC, formato "YYYY-MM-DD HH:MM:SS"
    return datetime.utcnow().strftime("%Y-%m-%d 00:00:00")


def _since_last_24h() -> str:
    return (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")


def render_dashboard(conn):
    st.header("Dashboard")
    counts = dashboard_counts(conn, since=_since_today())

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Promoções aprovadas hoje", counts["approved"])
    col2.metric("Alertas enviados hoje", counts["notified"])
    col3.metric("Duplicadas ignoradas", counts["duplicated"])
    col4.metric("Possíveis bugs", counts["bugs"])
    col5.metric("Ignoradas hoje", counts["ignored"])

    st.subheader("Top grupos de origem")
    if counts["top_groups"]:
        st.table([{"Grupo": row["source_chat_title"], "Promoções": row["total"]}
                   for row in counts["top_groups"]])
    else:
        st.info("Sem dados suficientes ainda.")

    st.subheader("Últimas promoções aprovadas")
    approved = list_promotions(conn, status="APPROVED", limit=20)
    if approved:
        st.table([
            {
                "Data": row["created_at"],
                "Título": row["title_guess"],
                "Preço": row["price"],
                "Score": row["score"],
                "Grupo": row["source_chat_title"],
            }
            for row in approved
        ])
    else:
        st.info("Nenhuma promoção aprovada ainda.")


def render_alertas(conn):
    st.header("Alertas")
    st.caption("Edição via interface ainda não implementada nesta fase — edite alerts.json diretamente.")
    alerts = list_alerts(conn)
    if alerts:
        st.table([dict(row) for row in alerts])
    else:
        st.info("Nenhum alerta cadastrado no banco ainda (alerts.json é a fonte atual).")


def render_promocoes(conn):
    st.header("Promoções")
    filtro = st.selectbox(
        "Filtro",
        ["Hoje", "Últimas 24h", "Apenas notificadas", "Apenas duplicadas", "Todas"],
    )

    since = None
    status = None
    if filtro == "Hoje":
        since = _since_today()
    elif filtro == "Últimas 24h":
        since = _since_last_24h()
    elif filtro == "Apenas notificadas":
        status = "APPROVED"

    rows = list_promotions(conn, since=since, status=status, limit=200)
    if not rows:
        st.info("Nenhuma promoção encontrada para este filtro.")
        return

    st.table([
        {
            "Data/hora": row["created_at"],
            "Título": row["title_guess"],
            "Preço": row["price"],
            "Status": row["status"],
            "Score": row["score"],
            "Link": row["clean_url"] or row["resolved_url"] or row["selected_original_url"],
            "Status do link": row["link_status"],
            "Grupo": row["source_chat_title"],
            "Repetições": row["repeat_count"],
        }
        for row in rows
    ])


def render_mensagens(conn):
    st.header("Mensagens Telegram")
    rows = list_raw_messages(conn, limit=200)
    if not rows:
        st.info("Nenhuma mensagem capturada ainda.")
        return

    st.table([
        {
            "Data": row["created_at"],
            "Grupo": row["chat_title"],
            "Texto": (row["message_text"] or "")[:200],
        }
        for row in rows
    ])


def main():
    st.set_page_config(page_title="PromoWatcher", layout="wide")
    st.title("PromoWatcher — Central Inteligente de Promoções")

    conn = _get_conn()

    tab_dashboard, tab_alertas, tab_promocoes, tab_mensagens = st.tabs(
        ["Dashboard", "Alertas", "Promoções", "Mensagens Telegram"]
    )
    with tab_dashboard:
        render_dashboard(conn)
    with tab_alertas:
        render_alertas(conn)
    with tab_promocoes:
        render_promocoes(conn)
    with tab_mensagens:
        render_mensagens(conn)


if __name__ == "__main__":
    main()
