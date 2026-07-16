from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.api.schemas import PriceHistoryPointOut, ProductDetail
from app.products.catalog_service import get_product_detail, list_price_history_windowed

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, conn=Depends(get_db)):
    detail = get_product_detail(conn, product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return detail


@router.get("/{product_id}/price-history", response_model=List[PriceHistoryPointOut])
def get_price_history(product_id: int, window: int = Query(30, ge=1, le=365), conn=Depends(get_db)):
    rows = list_price_history_windowed(conn, product_id, days=window)
    return [
        PriceHistoryPointOut(
            recorded_at=row["recorded_at"], price=row["price"],
            is_bug_candidate=bool(row["is_bug_candidate"]), deviation_percent=row["deviation_percent"],
        )
        for row in rows
    ]
