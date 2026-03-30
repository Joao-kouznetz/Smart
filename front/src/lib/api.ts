import type {
  AddCartItemPayload,
  Cart,
  LocationPromotionsPayload,
  Product,
  Promotion,
  RecommendationPayload,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = "Nao foi possivel concluir a requisicao.";

    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      message = response.statusText || message;
    }

    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export function fetchCart(cartId: string): Promise<Cart> {
  return requestJson<Cart>(`/cart/${cartId}`);
}

export function addCartItem(cartId: string, payload: AddCartItemPayload): Promise<Cart> {
  return requestJson<Cart>(`/cart/${cartId}/items`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCartItem(cartId: string, itemId: number): Promise<Cart> {
  return requestJson<Cart>(`/cart/${cartId}/items/${itemId}`, {
    method: "DELETE",
  });
}

export function checkoutCart(cartId: string): Promise<Cart> {
  return requestJson<Cart>(`/cart/${cartId}/checkout`, {
    method: "POST",
  });
}

export function searchProducts(query: string): Promise<Product[]> {
  const params = new URLSearchParams({ query });
  return requestJson<Product[]>(`/products/search?${params.toString()}`);
}

export function fetchStorePromotions(): Promise<Promotion[]> {
  return requestJson<Promotion[]>("/promotions");
}

export function fetchRecommendations(cartId: string): Promise<RecommendationPayload> {
  return requestJson<RecommendationPayload>(`/cart/${cartId}/recommendations`);
}

export function fetchLocationPromotions(cartId: string): Promise<LocationPromotionsPayload> {
  return requestJson<LocationPromotionsPayload>(`/cart/${cartId}/promotions/location`);
}
