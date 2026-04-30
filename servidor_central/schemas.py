from typing import Any, Literal

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
    algorithm_status: Literal["ready", "insufficient_data", "cache_missing", "product_not_in_graph"]
    recommendations: list[PromotionResponse]


class LocationPromotionsResponse(BaseModel):
    cart_id: str
    algorithm_status: Literal["ready", "insufficient_data", "cache_missing", "product_not_in_graph"]
    inferred_location: str | None = None
    current_product_barcode: str | None = None
    current_product_name: str | None = None
    graph_position: dict[str, Any] | None = None
    neighbors: list[dict[str, Any]] = Field(default_factory=list)
    promotions: list[PromotionResponse]


class LocationResponse(BaseModel):
    cart_id: str
    algorithm_status: Literal["ready", "insufficient_data", "cache_missing", "product_not_in_graph"]
    current_product_barcode: str | None = None
    current_product_name: str | None = None
    aisle: str | None = None
    graph_position: dict[str, Any] | None = None
    neighbors: list[dict[str, Any]] = Field(default_factory=list)


class LocationGraphRebuildRequest(BaseModel):
    start_at: str | None = None
    temporal_decay: bool = False
    half_life_days: float = Field(default=30.0, gt=0)
    decay_min_weight: float = Field(default=0.01, ge=0)


class LocationGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]
    meta: dict[str, Any]


class LocationGraphLinkNodeResponse(BaseModel):
    barcode: str
    name: str | None = None
    category: str | None = None
    aisle: str | None = None
    scan_count: int | None = None
    x: float | None = None
    y: float | None = None


class LocationGraphLinkSampleResponse(BaseModel):
    cart_id: str
    elapsed_seconds: float
    transition_at: str
    weight: float
    kept_after_lower: bool
    kept_after_upper: bool


class LocationGraphLinkAnalysisResponse(BaseModel):
    outlier_method: str | None = None
    lower_threshold_seconds: float
    upper_threshold_seconds: float | None = None
    dip_p_value: float | None = None
    dependency_warning: str | None = None
    min_raw_edge_samples: int | None = None
    min_clean_edge_samples: int | None = None
    raw_sample_count: int
    lower_cleaned_sample_count: int
    upper_cleaned_sample_count: int
    discarded_after_lower_threshold: int
    discarded_after_upper_threshold: int


class LocationGraphLinkDetailsResponse(BaseModel):
    source: str
    target: str
    source_node: LocationGraphLinkNodeResponse | None = None
    target_node: LocationGraphLinkNodeResponse | None = None
    link: dict[str, Any]
    analysis: LocationGraphLinkAnalysisResponse
    samples: list[LocationGraphLinkSampleResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database_path: str
