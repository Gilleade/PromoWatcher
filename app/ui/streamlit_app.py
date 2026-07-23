from datetime import datetime, timedelta

import streamlit as st

from app.config import get_config
from app.database import get_connection
from app.models import AlertDef
from app.rules.alert_matcher import load_alerts, save_alerts, sync_alerts_to_db
from app.services.promotion_service import (
    dashboard_counts,
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


def _lines_to_terms(text: str) -> list:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_optional_float(text: str):
    text = (text or "").strip()
    return float(text) if text else None


def _alert_form(key_prefix: str, alert):
    """Formulário de criação/edição de um alerta. Retorna um AlertDef com os
    valores submetidos, ou None se o formulário não foi submetido."""
    with st.form(key=f"form_{key_prefix}"):
        name = st.text_input("Nome", value=alert.name if alert else "", key=f"{key_prefix}_name")
        enabled = st.checkbox("Ativado", value=alert.enabled if alert else True, key=f"{key_prefix}_enabled")
        alert_type = st.selectbox(
            "Tipo", ["PRODUCT_RULE", "BUG_RULE"],
            index=(0 if not alert or alert.alert_type == "PRODUCT_RULE" else 1),
            key=f"{key_prefix}_type",
        )
        required = st.text_area(
            "Termos obrigatórios (um por linha)",
            value="\n".join(alert.required) if alert else "", key=f"{key_prefix}_required",
        )
        any_terms = st.text_area(
            "Termos opcionais — pelo menos um deve aparecer (um por linha)",
            value="\n".join(alert.any) if alert else "", key=f"{key_prefix}_any",
        )
        exclude = st.text_area(
            "Termos bloqueados (um por linha)",
            value="\n".join(alert.exclude) if alert else "", key=f"{key_prefix}_exclude",
        )
        col1, col2, col3 = st.columns(3)
        max_price = col1.text_input(
            "Preço máximo (vazio = sem limite)",
            value=str(alert.max_price) if alert and alert.max_price is not None else "",
            key=f"{key_prefix}_max_price",
        )
        min_discount = col2.text_input(
            "Desconto mínimo % (vazio = 0)",
            value=str(alert.min_discount_percent) if alert and alert.min_discount_percent is not None else "",
            key=f"{key_prefix}_min_discount",
        )
        min_score = col3.number_input(
            "Score mínimo", value=alert.min_score if alert else 0, step=1, key=f"{key_prefix}_min_score",
        )
        bug_mode = st.checkbox("Modo bug", value=alert.bug_mode if alert else False, key=f"{key_prefix}_bug_mode")
        send_to_telegram = st.checkbox(
            "Enviar ao Telegram quando aprovado",
            value=alert.send_to_telegram if alert else True, key=f"{key_prefix}_send",
        )

        submitted = st.form_submit_button("Salvar alterações" if alert else "Criar alerta")

    if not submitted:
        return None

    if not name.strip():
        st.error("O nome do alerta não pode ficar vazio.")
        return None

    return AlertDef(
        name=name.strip(),
        enabled=enabled,
        alert_type=alert_type,
        required=_lines_to_terms(required),
        any=_lines_to_terms(any_terms),
        exclude=_lines_to_terms(exclude),
        max_price=_parse_optional_float(max_price),
        min_discount_percent=_parse_optional_float(min_discount) or 0,
        bug_mode=bug_mode,
        min_score=int(min_score),
        send_to_telegram=send_to_telegram,
        id=alert.id if alert else None,
    )


def _persist_alerts(conn, config, alerts):
    save_alerts(config.alerts_file, alerts)
    sync_alerts_to_db(conn, alerts)


def render_alertas(conn):
    st.header("Alertas")
    st.caption(
        "Alertas são lidos e salvos em alerts.json (fonte da verdade). "
        "O watcher recarrega automaticamente em até 30s após qualquer mudança. "
        "Excluir um alerta remove-o de alerts.json; o histórico de promoções que "
        "já usaram esse alerta é preservado no banco."
    )

    flash = st.session_state.pop("_alert_flash", None)
    if flash:
        st.success(flash)

    config = get_config()
    alerts = load_alerts(config.alerts_file)
    existing_names = {a.name for a in alerts}

    with st.expander("+ Novo alerta"):
        new_alert = _alert_form("new", None)
        if new_alert:
            if new_alert.name in existing_names:
                st.error(f"Já existe um alerta chamado '{new_alert.name}'.")
            else:
                alerts.append(new_alert)
                _persist_alerts(conn, config, alerts)
                st.session_state["_alert_flash"] = f"Alerta '{new_alert.name}' criado."
                st.rerun()

    if not alerts:
        st.info("Nenhum alerta cadastrado ainda.")
        return

    for i, alert in enumerate(alerts):
        status = "✅ ativado" if alert.enabled else "⏸️ desativado"
        with st.expander(f"{alert.name} ({status})"):
            updated = _alert_form(f"edit_{i}", alert)
            if updated:
                if updated.name != alert.name and updated.name in existing_names:
                    st.error(f"Já existe um alerta chamado '{updated.name}'.")
                else:
                    alerts[i] = updated
                    _persist_alerts(conn, config, alerts)
                    st.session_state["_alert_flash"] = "Alterações salvas."
                    st.rerun()

            st.divider()
            confirm = st.checkbox("Confirmar exclusão", key=f"confirm_delete_{i}")
            if st.button("Excluir alerta", key=f"delete_{i}", disabled=not confirm):
                del alerts[i]
                save_alerts(config.alerts_file, alerts)
                st.session_state["_alert_flash"] = f"Alerta '{alert.name}' excluído."
                st.rerun()


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
