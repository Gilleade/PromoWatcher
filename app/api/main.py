from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, coupons, dashboard, favorites, feed, products

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


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
