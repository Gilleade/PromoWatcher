from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.api.schemas import CouponOut
from app.products.catalog_service import list_coupons

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.get("", response_model=List[CouponOut])
def get_coupons(status: str = Query("ACTIVE"), conn=Depends(get_db)):
    rows = list_coupons(conn, status=status)
    return [CouponOut(**dict(row)) for row in rows]
