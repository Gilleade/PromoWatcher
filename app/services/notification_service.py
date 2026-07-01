from typing import Optional

from app.models import AlertDef


def build_notification_text(*, alert: AlertDef, title_guess: Optional[str], price: Optional[float],
                             coupon: Optional[str], link_status: str, url: Optional[str],
                             source_chat_title: Optional[str], score: int, repeat_count: int,
                             reason: str) -> str:
    lines = ["🚨 PromoWatcher", f"Alerta: {alert.name}", f"Score: {score}"]
    if source_chat_title:
        lines.append(f"Origem: {source_chat_title}")
    lines.append(f"Repetições detectadas: {repeat_count}")
    lines.append("")

    if title_guess:
        lines.append("Produto:")
        lines.append(title_guess)
        lines.append("")

    if price is not None:
        lines.append(f"Preço: R$ {price:,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))
    if coupon:
        lines.append(f"Cupom: {coupon}")
    lines.append(f"Status do link: {link_status}")
    lines.append("")

    if url:
        lines.append("Link:")
        lines.append(url)
        lines.append("")

    lines.append("Motivo:")
    lines.append(reason)

    return "\n".join(lines)
