import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import admin, alerts, coupons, dashboard, favorites, feed, products
from app.config import get_config

app = FastAPI(title="PromoWatcher API", version="0.1.0")

# CORS liberado para o dev server do Vite (ferramenta pessoal local, sem
# exposição pública) — restrinja isso se algum dia for exposto fora da rede local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(coupons.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


# Fotos baixadas do Telegram para os produtos (ver
# app/products/product_service.py attach_product_image — o prefixo /media/
# construído lá precisa casar com este mount).
_config = get_config()
os.makedirs(_config.images_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=_config.images_dir), name="media")


# Build de produção do frontend (Vite) — serve o app estático quando existir.
# Em desenvolvimento (Bloco 11 em diante) o front roda em `npm run dev`
# separado (porta 5173, liberada no CORS acima); esse mount só entra em jogo
# depois de `npm run build`. Registrado por último para não sombrear as
# rotas /api/v1/* acima.
_WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
if _WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")
