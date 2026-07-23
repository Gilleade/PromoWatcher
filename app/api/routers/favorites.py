from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.schemas import ProductCard
from app.products.catalog_service import list_favorites

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=List[ProductCard])
def get_favorites(conn=Depends(get_db)):
    rows = list_favorites(conn)
    return [ProductCard(**dict(row)) for row in rows]
