from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.api.schemas import AlertIn, AlertOut
from app.config import Config, get_config
from app.models import AlertDef
from app.rules.alert_matcher import load_alerts, save_alerts, sync_alerts_to_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _load_synced(conn) -> Tuple[List[AlertDef], Config]:
    """alerts.json continua sendo a fonte da verdade (mesmo padrão da aba
    Alertas do Streamlit) — a API só lê/escreve nele e sincroniza com a
    tabela alerts para os ids ficarem estáveis."""
    config = get_config()
    alerts = load_alerts(config.alerts_file)
    return sync_alerts_to_db(conn, alerts), config


def _find_by_id(alerts: List[AlertDef], alert_id: int) -> AlertDef:
    alert = next((a for a in alerts if a.id == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return alert


@router.get("", response_model=List[AlertOut])
def list_alerts_endpoint(conn=Depends(get_db)):
    alerts, _ = _load_synced(conn)
    return [AlertOut(**vars(a)) for a in alerts]


@router.post("", response_model=AlertOut)
def create_alert(body: AlertIn, conn=Depends(get_db)):
    alerts, config = _load_synced(conn)
    if any(a.name == body.name for a in alerts):
        raise HTTPException(status_code=400, detail=f"Já existe um alerta chamado '{body.name}'.")

    alerts.append(AlertDef(**body.model_dump()))
    save_alerts(config.alerts_file, alerts)
    alerts = sync_alerts_to_db(conn, alerts)
    created = next(a for a in alerts if a.name == body.name)
    return AlertOut(**vars(created))


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, body: AlertIn, conn=Depends(get_db)):
    alerts, config = _load_synced(conn)
    _find_by_id(alerts, alert_id)
    if any(a.name == body.name and a.id != alert_id for a in alerts):
        raise HTTPException(status_code=400, detail=f"Já existe um alerta chamado '{body.name}'.")

    alerts = [AlertDef(**body.model_dump(), id=alert_id) if a.id == alert_id else a for a in alerts]
    save_alerts(config.alerts_file, alerts)
    alerts = sync_alerts_to_db(conn, alerts)
    return AlertOut(**vars(_find_by_id(alerts, alert_id)))


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, conn=Depends(get_db)):
    alerts, config = _load_synced(conn)
    target = _find_by_id(alerts, alert_id)
    alerts = [a for a in alerts if a.id != alert_id]
    save_alerts(config.alerts_file, alerts)
    return {"deleted": True, "name": target.name}


@router.post("/{alert_id}/toggle", response_model=AlertOut)
def toggle_alert(alert_id: int, conn=Depends(get_db)):
    alerts, config = _load_synced(conn)
    target = _find_by_id(alerts, alert_id)
    target.enabled = not target.enabled
    save_alerts(config.alerts_file, alerts)
    alerts = sync_alerts_to_db(conn, alerts)
    return AlertOut(**vars(_find_by_id(alerts, alert_id)))
