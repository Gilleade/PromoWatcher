from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.api.schemas import (
    FavoriteStatus,
    MergeRequest,
    MergeResult,
    PriceHistoryPointOut,
    ProductAlertIn,
    ProductAlertOut,
    ProductDetail,
    ProductStatusOut,
)
from app.products.catalog_service import get_product_detail, get_product_row, list_price_history_windowed
from app.products.product_service import merge_products, set_product_alert, set_product_blocked, toggle_favorite

router = APIRouter(prefix="/products", tags=["products"])


def _require_product(conn, product_id: int):
    product = get_product_row(conn, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product


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


@router.post("/{product_id}/favorite", response_model=FavoriteStatus)
def add_favorite(product_id: int, conn=Depends(get_db)):
    _require_product(conn, product_id)
    toggle_favorite(conn, product_id, favorited=True)
    return FavoriteStatus(product_id=product_id, is_favorite=True)


@router.delete("/{product_id}/favorite", response_model=FavoriteStatus)
def remove_favorite(product_id: int, conn=Depends(get_db)):
    _require_product(conn, product_id)
    toggle_favorite(conn, product_id, favorited=False)
    return FavoriteStatus(product_id=product_id, is_favorite=False)


@router.post("/{product_id}/alert", response_model=ProductAlertOut)
def set_alert(product_id: int, body: ProductAlertIn, conn=Depends(get_db)):
    _require_product(conn, product_id)
    set_product_alert(
        conn, product_id, enabled=body.enabled, max_price=body.max_price,
        send_to_telegram=body.send_to_telegram,
    )
    return ProductAlertOut(
        product_id=product_id, enabled=body.enabled, max_price=body.max_price,
        send_to_telegram=body.send_to_telegram,
    )


@router.post("/{product_id}/block", response_model=ProductStatusOut)
def block_product(product_id: int, conn=Depends(get_db)):
    _require_product(conn, product_id)
    set_product_blocked(conn, product_id, blocked=True)
    return ProductStatusOut(product_id=product_id, status="BLOCKED")


@router.post("/{product_id}/unblock", response_model=ProductStatusOut)
def unblock_product(product_id: int, conn=Depends(get_db)):
    _require_product(conn, product_id)
    set_product_blocked(conn, product_id, blocked=False)
    return ProductStatusOut(product_id=product_id, status="ACTIVE")


@router.post("/{product_id}/merge", response_model=MergeResult)
def merge_into_product(product_id: int, body: MergeRequest, conn=Depends(get_db)):
    _require_product(conn, product_id)
    _require_product(conn, body.source_product_id)
    try:
        merge_products(
            conn, source_product_id=body.source_product_id, target_product_id=product_id,
            reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MergeResult(source_product_id=body.source_product_id, target_product_id=product_id)
