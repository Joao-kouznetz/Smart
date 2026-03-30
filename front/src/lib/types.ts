export interface Product {
  barcode: string;
  name: string;
  price: number;
  category?: string | null;
  aisle?: string | null;
}

export interface CartItem {
  item_id: number;
  barcode: string;
  name: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  category?: string | null;
  aisle?: string | null;
}

export interface Cart {
  cart_id: string;
  items: CartItem[];
  total_items: number;
  total_amount: number;
  updated_at: string;
}

export interface Promotion {
  id: string;
  title: string;
  description?: string | null;
  product_barcode?: string | null;
  discount_type?: string | null;
  discount_value?: number | null;
  aisle?: string | null;
}

export interface RecommendationPayload {
  cart_id: string;
  algorithm_status: "not_implemented";
  recommendations: Promotion[];
}

export interface LocationPromotionsPayload {
  cart_id: string;
  algorithm_status: "not_implemented";
  inferred_location?: string | null;
  promotions: Promotion[];
}

export interface AddCartItemPayload {
  barcode: string;
  quantity: number;
}
