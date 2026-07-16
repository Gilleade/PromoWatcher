from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.api.schemas import MatchQueueItem, MatchQueueResolveRequest, MatchQueueResolveResult, ProductAdmin
from app.products.catalog_service import list_products_for_admin, list_review_queue
from app.products.product_service import resolve_match_queue_item_manually

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/products", response_model=List[ProductAdmin])
def get_products_admin(status: Optional[str] = None, search: Optional[str] = None, conn=Depends(get_db)):
    rows = list_products_for_admin(conn, status=status, search=search)
    return [ProductAdmin(**dict(row)) for row in rows]


@router.get("/match-queue", response_model=List[MatchQueueItem])
def get_match_queue(status: Optional[str] = Query(None), conn=Depends(get_db)):
    rows = list_review_queue(conn, status=status)
    return [MatchQueueItem(**dict(row)) for row in rows]


@router.post("/match-queue/{item_id}/resolve", response_model=MatchQueueResolveResult)
def resolve_match_queue(item_id: int, body: MatchQueueResolveRequest, conn=Depends(get_db)):
    try:
        result = resolve_match_queue_item_manually(
            conn, item_id, action=body.action, product_id=body.product_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MatchQueueResolveResult(**result)
