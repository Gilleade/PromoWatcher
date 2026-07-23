from typing import Optional

from app.models import AlertDef


def build_notification_text(*, alert: Optional[AlertDef], title_guess: Optional[str],
                             price: Optional[float], coupon: Optional[str], link_status: str,
                             url: Optional[str], source_chat_title: Optional[str],
                             score: Optional[int], repeat_count: int, reason: str,
                             alert_name: Optional[str] = None,
                             installment_count: Optional[int] = None,
                             installment_price: Optional[float] = None,
                             installment_no_interest: Optional[bool] = None) -> str:
    resolved_alert_name = alert.name if alert is not None else alert_name or "Produto monitorado"
    lines = ["🚨 PromoWatcher", f"Alerta: {resolved_alert_name}"]
    if score is not None:
        lines.append(f"Score: {score}")
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
    if installment_count and installment_price is not None:
        parcela = f"R$ {installment_price:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        juros = " sem juros" if installment_no_interest else ""
        lines.append(f"Parcelado: {installment_count}x de {parcela}{juros}")
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
