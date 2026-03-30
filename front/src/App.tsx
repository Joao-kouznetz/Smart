import { useEffect, useRef, useState } from "react";
import Keyboard from "react-simple-keyboard";
import "react-simple-keyboard/build/css/index.css";

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

function App() {
  const [deviceId] = useState(() => getResolvedDeviceId());
  const keyboardRef = useRef<any>(null);
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

  async function runSearch(query: string) {
    const normalizedQuery = query.trim();

    if (normalizedQuery.length < 2) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    setSearching(true);
    setSearchError(null);

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

  // Real-time search with debounce
  useEffect(() => {
    const timeout = setTimeout(() => {
      void runSearch(searchQuery);
    }, 300);

    return () => clearTimeout(timeout);
  }, [searchQuery]);

  // Sync physical keyboard input with virtual keyboard state
  useEffect(() => {
    if (!keyboardOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept if typing in a real input (like barcode)
      if (document.activeElement?.tagName === "INPUT" && document.activeElement.id !== "search-query-overlay") {
        return;
      }

      if (e.key === "Enter") {
        setKeyboardOpen(false);
        setResultsOverlayOpen(true);
      } else if (e.key === "Escape") {
        setKeyboardOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [keyboardOpen]);

  function onVirtualKeyboardChange(input: string) {
    setSearchQuery(input);
  }

  function onVirtualKeyPress(button: string) {
    if (button === "{enter}") {
      setKeyboardOpen(false);
      setResultsOverlayOpen(true);
    }
    if (button === "{escape}") {
      setKeyboardOpen(false);
    }
  }

  function onPhysicalInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const input = event.target.value;
    setSearchQuery(input);
    keyboardRef.current?.setInput(input);
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

        <div className="layout-grid">
          <section className="workspace-column workspace-column--left">
            <PromotionRail
              emptyLabel="As recomendacoes aparecerao aqui assim que a API responder."
              loading={loadingPromotions}
              promotions={recommendedPromotions?.recommendations ?? []}
              subtitle="Recomendado"
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
              subtitle="Ofertas da Loja"
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
                <p className="eyebrow">Busca profissional</p>
                <h2>O que você procura hoje?</h2>
              </div>
              <button
                className="touch-button touch-button--ghost overlay-card__close"
                onClick={() => setKeyboardOpen(false)}
                type="button"
              >
                Fechar
              </button>
            </div>

            <div className="search-bar search-bar--active">
              <SearchIcon />
              <input
                autoFocus
                id="search-query-overlay"
                className="search-bar__input"
                onChange={onPhysicalInputChange}
                placeholder="Pesquisar produto pelo nome"
                type="text"
                value={searchQuery}
              />
            </div>

            {searchError ? <div className="empty-card">{searchError}</div> : null}

            <div className="keyboard-container">
              <Keyboard
                keyboardRef={(r) => (keyboardRef.current = r)}
                onChange={onVirtualKeyboardChange}
                onKeyPress={onVirtualKeyPress}
                inputName="searchQuery"
                layout={{
                  default: [
                    "q w e r t y u i o p",
                    "a s d f g h j k l",
                    "z x c v b n m {backspace}",
                    "{space} {enter}",
                  ],
                }}
                display={{
                  "{enter}": "pesquisar",
                  "{backspace}": "apagar",
                  "{space}": "espaço",
                }}
              />
            </div>
            
            <div className="keyboard-results-preview">
              {searching ? (
                <div className="search-status">Buscando...</div>
              ) : searchResults.length > 0 ? (
                <div className="search-status">Encontramos {searchResults.length} produtos. Clique em pesquisar para ver todos.</div>
              ) : searchQuery.length >= 2 ? (
                <div className="search-status">Nenhum produto encontrado.</div>
              ) : null}
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
