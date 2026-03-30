import { useEffect, useState } from "react";

import { CartItemsPanel } from "./components/CartItemsPanel";
import { PromotionRail } from "./components/PromotionRail";
import { QuantityStepper } from "./components/QuantityStepper";
import {
  addCartItem,
  ApiError,
  checkoutCart,
  deleteCartItem,
  fetchCart,
  fetchLocationPromotions,
  fetchRecommendations,
  fetchStorePromotions,
  searchProducts,
} from "./lib/api";
import { getResolvedDeviceId } from "./lib/deviceId";
import type {
  Cart,
  CartItem,
  LocationPromotionsPayload,
  Product,
  Promotion,
  RecommendationPayload,
} from "./lib/types";

function SearchIcon() {
  return (
    <svg
      aria-hidden="true"
      className="search-bar__icon"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle cx="11" cy="11" r="6.75" stroke="currentColor" strokeWidth="2" />
      <path d="M16.2 16.2L20 20" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
    </svg>
  );
}

const KEYBOARD_ROWS = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["z", "x", "c", "v", "b", "n", "m"],
] as const;

function App() {
  const [deviceId] = useState(() => getResolvedDeviceId());
  const [cart, setCart] = useState<Cart | null>(null);
  const [storePromotions, setStorePromotions] = useState<Promotion[]>([]);
  const [recommendedPromotions, setRecommendedPromotions] = useState<RecommendationPayload | null>(null);
  const [locationPromotions, setLocationPromotions] = useState<LocationPromotionsPayload | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [barcodeInput, setBarcodeInput] = useState("");
  const [manualQuantity, setManualQuantity] = useState(1);
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [loadingPromotions, setLoadingPromotions] = useState(true);
  const [searching, setSearching] = useState(false);
  const [busyItemId, setBusyItemId] = useState<number | null>(null);
  const [submittingAction, setSubmittingAction] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [bannerMessage, setBannerMessage] = useState<string | null>(null);
  const [bannerTone, setBannerTone] = useState<"info" | "error" | "success">("info");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  const [resultsOverlayOpen, setResultsOverlayOpen] = useState(false);

  async function loadCart() {
    const nextCart = await fetchCart(deviceId);
    setCart(nextCart);
    return nextCart;
  }

  async function loadPromotionPanels() {
    setLoadingPromotions(true);
    try {
      const [store, recommendations, location] = await Promise.all([
        fetchStorePromotions(),
        fetchRecommendations(deviceId),
        fetchLocationPromotions(deviceId),
      ]);
      setStorePromotions(store);
      setRecommendedPromotions(recommendations);
      setLocationPromotions(location);
    } finally {
      setLoadingPromotions(false);
    }
  }

  async function loadDashboard() {
    setLoadingDashboard(true);
    setBannerMessage(null);

    try {
      await Promise.all([loadCart(), loadPromotionPanels()]);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Nao foi possivel sincronizar o carrinho com o servidor central.";
      setBannerTone("error");
      setBannerMessage(message);
    } finally {
      setLoadingDashboard(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, [deviceId]);

  async function refreshAfterCartChange(nextCart?: Cart) {
    if (nextCart) {
      setCart(nextCart);
    } else {
      await loadCart();
    }

    await loadPromotionPanels();
  }

  async function handleAddItem(barcode: string, quantity: number) {
    const normalizedBarcode = barcode.trim();
    if (!normalizedBarcode) {
      setBannerTone("error");
      setBannerMessage("Informe um barcode valido para adicionar o produto.");
      return;
    }

    setSubmittingAction(true);
    setBannerTone("info");
    setBannerMessage("Adicionando produto ao carrinho...");

    try {
      const nextCart = await addCartItem(deviceId, {
        barcode: normalizedBarcode,
        quantity,
      });
      await refreshAfterCartChange(nextCart);
      setSearchQuery("");
      setSearchResults([]);
      setResultsOverlayOpen(false);
      setBarcodeInput("");
      setManualQuantity(1);
      setBannerTone("success");
      setBannerMessage("Produto adicionado com sucesso. Toque para continuar comprando.");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Nao foi possivel adicionar o produto.";
      setBannerTone("error");
      setBannerMessage(message);
    } finally {
      setSubmittingAction(false);
    }
  }

  async function handleRemoveItem(item: CartItem) {
    setBusyItemId(item.item_id);
    setBannerTone("info");
    setBannerMessage(`Removendo ${item.name} do carrinho...`);

    try {
      const nextCart = await deleteCartItem(deviceId, item.item_id);
      await refreshAfterCartChange(nextCart);
      setBannerTone("success");
      setBannerMessage("Item removido do carrinho.");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Nao foi possivel remover o item.";
      setBannerTone("error");
      setBannerMessage(message);
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleCheckout() {
    setCheckoutLoading(true);
    setBannerTone("info");
    setBannerMessage("Finalizando a compra e limpando o carrinho...");

    try {
      const nextCart = await checkoutCart(deviceId);
      await refreshAfterCartChange(nextCart);
      setBannerTone("success");
      setBannerMessage("Compra finalizada. O carrinho esta pronto para a proxima jornada.");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Nao foi possivel finalizar a compra.";
      setBannerTone("error");
      setBannerMessage(message);
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function runSearch() {
    const normalizedQuery = searchQuery.trim();

    if (normalizedQuery.length < 2) {
      setSearchError("Digite pelo menos 2 letras para pesquisar.");
      return;
    }

    setSearching(true);
    setSearchError(null);
    setKeyboardOpen(false);
    setResultsOverlayOpen(true);

    try {
      const products = await searchProducts(normalizedQuery);
      setSearchResults(products);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Nao foi possivel buscar produtos agora.";
      setSearchError(message);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleKeyboardKey(key: string) {
    if (key === "ENTER") {
      void runSearch();
      return;
    }

    if (key === "BACKSPACE") {
      setSearchQuery((current) => current.slice(0, -1));
      return;
    }

    if (key === "SPACE") {
      setSearchQuery((current) => `${current} `);
      return;
    }

    if (key === "CLEAR") {
      setSearchQuery("");
      setSearchError(null);
      return;
    }

    setSearchQuery((current) => `${current}${key}`);
    setSearchError(null);
  }

  return (
    <main className="app-shell">
      <div className="app-shell__backdrop" />
      <div className="dashboard-shell">
        <header className="top-strip">
          <button
            aria-haspopup="dialog"
            className="search-bar search-bar--button"
            onClick={() => {
              setKeyboardOpen(true);
              setSearchError(null);
            }}
            type="button"
          >
            <SearchIcon />
            <input
              aria-label="Pesquisar produto pelo nome"
              className="search-bar__input"
              id="search-query"
              onFocus={() => setKeyboardOpen(true)}
              placeholder="Pesquisar produto pelo nome"
              readOnly
              type="search"
              value={searchQuery}
            />
          </button>

          <div className="device-card">
            <span className="device-card__label">Carrinho</span>
            <strong>{deviceId}</strong>
          </div>
        </header>

        {bannerMessage ? (
          <div className={`status-banner status-banner--${bannerTone}`} role="status">
            {bannerMessage}
          </div>
        ) : null}

        <div className="layout-grid">
          <section className="workspace-column workspace-column--left">
            <PromotionRail
              emptyLabel="As recomendacoes aparecerao aqui assim que a API responder."
              loading={loadingPromotions}
              promotions={recommendedPromotions?.recommendations ?? []}
              subtitle="Promoções para Você"
              title="Para você"
            />

            <PromotionRail
              emptyLabel="O supermercado ainda nao enviou promocoes gerais."
              loading={loadingPromotions}
              promotions={Array.from(
                new Map(
                  [
                    ...storePromotions,
                    ...(locationPromotions?.promotions ?? []),
                    ...(recommendedPromotions?.recommendations ?? []),
                  ].map((p) => [p.id, p])
                ).values()
              )}
              subtitle="Promoção Geral"
              title="Geral"
            />
          </section>

          <CartItemsPanel
            busyItemId={busyItemId}
            cart={cart}
            checkoutLoading={checkoutLoading}
            loading={loadingDashboard}
            onCheckout={() => void handleCheckout()}
            onRemoveItem={(item) => void handleRemoveItem(item)}
          />
        </div>
      </div>

      {keyboardOpen ? (
        <div
          aria-modal="true"
          className="overlay-shell"
          role="dialog"
          aria-label="Teclado virtual de busca"
        >
          <div className="overlay-card overlay-card--keyboard">
            <div className="overlay-card__header">
              <div>
                <p className="eyebrow">Busca touch</p>
                <h2>Digite o nome do produto</h2>
              </div>
              <button
                className="touch-button touch-button--ghost overlay-card__close"
                onClick={() => setKeyboardOpen(false)}
                type="button"
              >
                Fechar
              </button>
            </div>

            <div className="keyboard-display" aria-live="polite">
              {searchQuery || "Toque nas teclas para compor a busca"}
            </div>

            {searchError ? <div className="empty-card">{searchError}</div> : null}

            <div className="keyboard-grid" role="group" aria-label="Teclado virtual">
              {KEYBOARD_ROWS.map((row, index) => (
                <div className="keyboard-row" key={`row-${index}`}>
                  {row.map((key) => (
                    <button
                      className="touch-button touch-button--ghost keyboard-key"
                      key={key}
                      onClick={() => handleKeyboardKey(key)}
                      type="button"
                    >
                      {key}
                    </button>
                  ))}
                </div>
              ))}

              <div className="keyboard-row keyboard-row--actions">
                <button
                  className="touch-button touch-button--ghost keyboard-key keyboard-key--wide"
                  onClick={() => handleKeyboardKey("SPACE")}
                  type="button"
                >
                  Espaco
                </button>
                <button
                  className="touch-button touch-button--ghost keyboard-key"
                  onClick={() => handleKeyboardKey("BACKSPACE")}
                  type="button"
                >
                  Apagar
                </button>
                <button
                  className="touch-button touch-button--ghost keyboard-key"
                  onClick={() => handleKeyboardKey("CLEAR")}
                  type="button"
                >
                  Limpar
                </button>
                <button
                  className="touch-button touch-button--primary keyboard-key keyboard-key--enter"
                  onClick={() => handleKeyboardKey("ENTER")}
                  type="button"
                >
                  Enter
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {resultsOverlayOpen ? (
        <div
          aria-modal="true"
          className="overlay-shell"
          role="dialog"
          aria-label="Resultados da pesquisa"
        >
          <div className="overlay-card overlay-card--results">
            <div className="overlay-card__header">
              <div>
                <p className="eyebrow">Resultados</p>
                <h2>{searchQuery.trim() ? `Produtos para "${searchQuery}"` : "Produtos encontrados"}</h2>
              </div>
              <button
                className="touch-button touch-button--ghost overlay-card__close"
                onClick={() => setResultsOverlayOpen(false)}
                type="button"
              >
                Fechar
              </button>
            </div>

            <div className="overlay-results" role="list" aria-label="Resultados da pesquisa">
              {searching ? <div className="empty-card">Buscando produtos...</div> : null}
              {!searching && searchError ? <div className="empty-card">{searchError}</div> : null}
              {!searching && !searchError && searchResults.length === 0 ? (
                <div className="empty-card">Nenhum produto encontrado para esse termo.</div>
              ) : null}
              {!searching &&
                !searchError &&
                searchResults.map((product) => (
                  <article className="search-result-card" key={product.barcode} role="listitem">
                    <div>
                      <h3>{product.name}</h3>
                      <p>
                        Barcode {product.barcode}
                        {product.category ? ` • ${product.category}` : ""}
                        {product.aisle ? ` • Corredor ${product.aisle}` : ""}
                      </p>
                      <strong>R$ {product.price.toFixed(2)}</strong>
                    </div>
                    <button
                      className="touch-button touch-button--primary"
                      disabled={submittingAction}
                      onClick={() => void handleAddItem(product.barcode, 1)}
                      type="button"
                    >
                      Adicionar
                    </button>
                  </article>
                ))}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default App;
