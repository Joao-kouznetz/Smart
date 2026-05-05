import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function mockJsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 404 ? "Not Found" : "OK",
    json: async () => payload,
  } as Response);
}

function createStatefulFetchMock() {
  let cart = {
    cart_id: "device-cart-7",
    items: [
      {
        item_id: 1,
        barcode: "7891000100103",
        name: "Leite Integral 1L",
        quantity: 1,
        unit_price: 5.99,
        subtotal: 5.99,
        category: "Laticinios",
        aisle: "A1",
      },
    ],
    total_items: 1,
    total_amount: 5.99,
    updated_at: "2026-03-29T10:00:00+00:00",
  };

  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (method === "GET" && url === "/cart/device-cart-7") {
      return mockJsonResponse(cart);
    }

    if (method === "GET" && url === "/promotions") {
      return mockJsonResponse([
        {
          id: "store-1",
          title: "Oferta da loja",
          description: "Promocao geral do supermercado",
          product_barcode: "7891000100104",
          discount_type: "fixed",
          discount_value: 5,
          aisle: "B2",
        },
      ]);
    }

    if (method === "GET" && url === "/cart/device-cart-7/recommendations") {
      return mockJsonResponse({
        cart_id: "device-cart-7",
        algorithm_status: "not_implemented",
        recommendations: [
          {
            id: "rec-1",
            title: "Promocao para voce",
            description: "Boilerplate de recomendacao",
            product_barcode: "7891000100103",
            discount_type: "percentage",
            discount_value: 10,
            aisle: "A1",
          },
        ],
      });
    }

    if (method === "GET" && url === "/cart/device-cart-7/promotions/location") {
      return mockJsonResponse({
        cart_id: "device-cart-7",
        algorithm_status: "not_implemented",
        inferred_location: "A1",
        promotions: [
          {
            id: "loc-1",
            title: "Perto de voce",
            description: "Promocao contextual",
            product_barcode: null,
            discount_type: "percentage",
            discount_value: 8,
            aisle: "A1",
          },
        ],
      });
    }

  if (method === "GET" && url === "/products/search?query=cafe") {
      return mockJsonResponse([
        {
          barcode: "7891000100104",
          name: "Cafe Torrado 500g",
          price: 18.75,
          category: "Bebidas",
          aisle: "B2",
        },
      ]);
    }

    if (method === "GET" && url === "/products/search?query=mac") {
      return mockJsonResponse([
        {
          barcode: "7891000100105",
          name: "Macarrao Espaguete 500g",
          price: 7.2,
          category: "Mercearia",
          aisle: "D4",
        },
      ]);
    }

    if (method === "POST" && url === "/cart/device-cart-7/items") {
      const payload = JSON.parse(String(init?.body ?? "{}"));

      if (payload.barcode === "7891000100104") {
        cart = {
          ...cart,
          items: [
            ...cart.items,
            {
              item_id: 2,
              barcode: "7891000100104",
              name: "Cafe Torrado 500g",
              quantity: payload.quantity,
              unit_price: 18.75,
              subtotal: 18.75 * payload.quantity,
              category: "Bebidas",
              aisle: "B2",
            },
          ],
          total_items: cart.total_items + payload.quantity,
          total_amount: Number((cart.total_amount + 18.75 * payload.quantity).toFixed(2)),
        };
      }

      if (payload.barcode === "7891000100105") {
        cart = {
          ...cart,
          items: [
            ...cart.items,
            {
              item_id: 3,
              barcode: "7891000100105",
              name: "Macarrao Espaguete 500g",
              quantity: payload.quantity,
              unit_price: 7.2,
              subtotal: 7.2 * payload.quantity,
              category: "Mercearia",
              aisle: "D4",
            },
          ],
          total_items: cart.total_items + payload.quantity,
          total_amount: Number((cart.total_amount + 7.2 * payload.quantity).toFixed(2)),
        };
      }

      return mockJsonResponse(cart, 201);
    }

    if (method === "DELETE" && url === "/cart/device-cart-7/items/1") {
      cart = {
        ...cart,
        items: cart.items.filter((item) => item.item_id !== 1),
        total_items: 0,
        total_amount: 0,
      };
      return mockJsonResponse(cart);
    }

    if (method === "POST" && url === "/cart/device-cart-7/checkout") {
      cart = {
        ...cart,
        items: [],
        total_items: 0,
        total_amount: 0,
      };
      return mockJsonResponse(cart);
    }

    return mockJsonResponse({ detail: `Unhandled ${method} ${url}` }, 500);
  });

  return fetchMock;
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/app?deviceId=device-cart-7");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the cart dashboard with the resolved device id", async () => {
    const fetchMock = createStatefulFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(screen.getByLabelText("Pesquisar produto pelo nome")).toBeInTheDocument();
    expect(await screen.findByText("device-cart-7")).toBeInTheDocument();
    expect(await screen.findByText("Leite Integral 1L")).toBeInTheDocument();
    expect((await screen.findAllByText("Promocao para voce")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Oferta da loja")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finalizar compra" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/cart/device-cart-7", expect.anything());
  });

  it("adds an item from search results", async () => {
    const fetchMock = createStatefulFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("Leite Integral 1L");
    await user.click(screen.getByLabelText("Pesquisar produto pelo nome"));
    expect(await screen.findByRole("dialog", { name: "Busca de produtos" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Comece a digitar o nome do produto..."), "cafe");

    expect(await screen.findByText("Cafe Torrado 500g")).toBeInTheDocument();
    const addButton = await screen.findByRole("button", { name: "Adicionar" });
    await user.click(addButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/cart/device-cart-7/items",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ barcode: "7891000100104", quantity: 1 }),
        }),
      );
    });

    expect((await screen.findAllByText("Cafe Torrado 500g")).length).toBeGreaterThan(0);
  });

  it("opens the search keyboard and keeps results in an overlay", async () => {
    const fetchMock = createStatefulFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("Leite Integral 1L");
    await user.click(screen.getByLabelText("Pesquisar produto pelo nome"));

    expect(await screen.findByRole("dialog", { name: "Busca de produtos" })).toBeInTheDocument();
    expect(screen.getByText("Digite pelo menos 2 letras para buscar.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Resultados da pesquisa" })).not.toBeInTheDocument();
  });

  it("finalizes the purchase from the cart panel", async () => {
    const fetchMock = createStatefulFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("Leite Integral 1L");
    await user.click(screen.getByRole("button", { name: "Finalizar compra" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/cart/device-cart-7/checkout",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
