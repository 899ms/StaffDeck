from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mock", tags=["mock"])


class MockOrderQueryRequest(BaseModel):
    order_id: str


class MockProductPurchaseRequest(BaseModel):
    user_id: str = "user_demo"
    product_id: str
    sku_id: str | None = None
    quantity: int = Field(default=1, ge=1, le=99)
    payment_method: str = "mock_balance"


class MockOrderAddRequest(BaseModel):
    user_id: str = "user_demo"
    order_id: str | None = None
    product_id: str
    sku_id: str | None = None
    quantity: int = Field(default=1, ge=1, le=99)
    status: str = "created"


@router.post("/order/query")
def mock_order_query(request: MockOrderQueryRequest) -> dict[str, Any]:
    if request.order_id.upper().startswith("HIS"):
        return {
            "order_id": request.order_id,
            "found": False,
            "source": "primary_order_center",
            "results": [],
            "miss_reason": "primary_order_center_miss",
            "hint": "主订单中心未命中，可尝试历史订单查询。",
        }
    signed_days = 3 if request.order_id == "A123456" else 16
    return {
        "order_id": request.order_id,
        "found": True,
        "source": "primary_order_center",
        "status": "signed",
        "signed_days": signed_days,
        "refundable": signed_days <= 7,
    }


@router.post("/order/archive-query")
def mock_order_archive_query(request: MockOrderQueryRequest) -> dict[str, Any]:
    return {
        "order_id": request.order_id,
        "found": True,
        "source": "archive_order_center",
        "status": "signed",
        "signed_days": 4,
        "refundable": True,
        "archive_reason": "订单已归档到历史订单中心",
        "recommendation": "该历史订单签收 4 天，当前可继续发起售后退款审核。",
    }


@router.post("/product/purchase")
def mock_product_purchase(request: MockProductPurchaseRequest) -> dict[str, Any]:
    unit_price = _mock_price(request.product_id)
    total_amount = unit_price * Decimal(request.quantity)
    order_id = f"MOCK{uuid4().hex[:10].upper()}"
    return {
        "order_id": order_id,
        "purchase_id": f"PUR{uuid4().hex[:10].upper()}",
        "user_id": request.user_id,
        "product_id": request.product_id,
        "sku_id": request.sku_id,
        "quantity": request.quantity,
        "unit_price": float(unit_price),
        "total_amount": float(total_amount),
        "currency": "CNY",
        "payment_method": request.payment_method,
        "payment_status": "paid",
        "order_status": "paid",
        "created_at": _now_iso(),
    }


@router.post("/order/add")
def mock_order_add(request: MockOrderAddRequest) -> dict[str, Any]:
    unit_price = _mock_price(request.product_id)
    total_amount = unit_price * Decimal(request.quantity)
    return {
        "order_id": request.order_id or f"ADD{uuid4().hex[:10].upper()}",
        "user_id": request.user_id,
        "product_id": request.product_id,
        "sku_id": request.sku_id,
        "quantity": request.quantity,
        "unit_price": float(unit_price),
        "total_amount": float(total_amount),
        "currency": "CNY",
        "status": request.status,
        "created_at": _now_iso(),
    }


def _mock_price(product_id: str) -> Decimal:
    catalog = {
        "SKU-001": Decimal("99.00"),
        "SKU-002": Decimal("199.00"),
        "SKU-003": Decimal("299.00"),
    }
    return catalog.get(product_id, Decimal("129.00"))


def _now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat()
