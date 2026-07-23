from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.api.schemas import ProductCard
from app.products.catalog_service import list_feed_products

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=List[ProductCard])
def get_feed(category: Optional[str] = None, limit: int = Query(50, le=200),
             offset: int = Query(0, ge=0), conn=Depends(get_db)):
    rows = list_feed_products(conn, category=category, limit=limit, offset=offset)
    return [ProductCard(**dict(row)) for row in rows]
