from typing import Literal

from pydantic import BaseModel, Field


class AddCartItemRequest(BaseModel):
    barcode: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class ProductResponse(BaseModel):
    barcode: str
    name: str
    price: float = Field(ge=0)
    category: str | None = None
    aisle: str | None = None


class CartItemResponse(BaseModel):
    item_id: int
    barcode: str
    name: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    subtotal: float = Field(ge=0)
    category: str | None = None
    aisle: str | None = None


class CartResponse(BaseModel):
    cart_id: str
    items: list[CartItemResponse]
    total_items: int = Field(ge=0)
    total_amount: float = Field(ge=0)
    updated_at: str


class PromotionResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    product_barcode: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    aisle: str | None = None


class RecommendationResponse(BaseModel):
    cart_id: str
    algorithm_status: Literal["not_implemented"]
    recommendations: list[PromotionResponse]


class LocationPromotionsResponse(BaseModel):
    cart_id: str
    algorithm_status: Literal["not_implemented"]
    inferred_location: str | None = None
    promotions: list[PromotionResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database_path: str
