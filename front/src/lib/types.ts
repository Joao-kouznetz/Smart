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
  algorithm_status: AlgorithmStatus;
  recommendations: Promotion[];
}

export interface LocationPromotionsPayload {
  cart_id: string;
  algorithm_status: AlgorithmStatus;
  inferred_location?: string | null;
  current_product_barcode?: string | null;
  current_product_name?: string | null;
  graph_position?: LocationGraphNode | null;
  neighbors: LocationGraphNeighbor[];
  promotions: Promotion[];
}

export type AlgorithmStatus = "ready" | "insufficient_data" | "cache_missing" | "product_not_in_graph";

export interface LocationGraphNode {
  id: string;
  barcode: string;
  name: string;
  category?: string | null;
  aisle?: string | null;
  scan_count: number;
  x?: number;
  y?: number;
}

export interface LocationGraphLink {
  source: string | LocationGraphNode;
  target: string | LocationGraphNode;
  transition_count: number;
  weighted_transition_count: number;
  avg_elapsed_seconds: number;
  p25_elapsed_seconds: number;
  min_elapsed_seconds: number;
  max_elapsed_seconds: number;
  strength: number;
  visual_distance: number;
}

export interface LocationGraphPayload {
  nodes: LocationGraphNode[];
  links: LocationGraphLink[];
  meta: Record<string, unknown>;
}

export interface LocationGraphNeighbor {
  barcode: string;
  name?: string | null;
  aisle?: string | null;
  x?: number | null;
  y?: number | null;
  avg_elapsed_seconds?: number | null;
  transition_count?: number | null;
  strength?: number | null;
}

export interface AddCartItemPayload {
  barcode: string;
  quantity: number;
}
