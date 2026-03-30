import type { Cart, CartItem } from "../lib/types";

interface CartItemsPanelProps {
  cart: Cart | null;
  loading: boolean;
  busyItemId?: number | null;
  checkoutLoading?: boolean;
  onRemoveItem: (item: CartItem) => void;
  onCheckout: () => void;
}

export function CartItemsPanel({
  cart,
  loading,
  busyItemId = null,
  checkoutLoading = false,
  onRemoveItem,
  onCheckout,
}: CartItemsPanelProps) {
  return (
    <section className="panel cart-panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Compra atual</p>
          <h2>Resumo do carrinho</h2>
        </div>
        <span className="panel__badge">Toque</span>
      </div>

      <div className="cart-summary">
        <div>
          <span className="cart-summary__label">Itens</span>
          <strong>{cart?.total_items ?? 0}</strong>
        </div>
        <div>
          <span className="cart-summary__label">Total</span>
          <strong>R$ {(cart?.total_amount ?? 0).toFixed(2)}</strong>
        </div>
      </div>

      <div className="cart-panel__body">
        <div className="cart-items-scroll">
          {loading ? (
            <div className="empty-card">Sincronizando o carrinho...</div>
          ) : cart && cart.items.length > 0 ? (
            cart.items.map((item) => (
              <article className="cart-item-card" key={item.item_id}>
                <div className="cart-item-card__content">
                  <div className="cart-item-card__topline">
                    <h3>{item.name}</h3>
                    <span className="cart-item-card__subtotal">R$ {item.subtotal.toFixed(2)}</span>
                  </div>
                  <p className="cart-item-card__meta">
                    Barcode {item.barcode}
                    {item.category ? ` • ${item.category}` : ""}
                    {item.aisle ? ` • Corredor ${item.aisle}` : ""}
                  </p>
                  <div className="cart-item-card__chips">
                    <span className="chip">Qtd. {item.quantity}</span>
                    <span className="chip">Unit. R$ {item.unit_price.toFixed(2)}</span>
                  </div>
                </div>
                <button
                  className="touch-button touch-button--danger"
                  disabled={busyItemId === item.item_id}
                  onClick={() => onRemoveItem(item)}
                  type="button"
                >
                  {busyItemId === item.item_id ? "Removendo..." : "Remover"}
                </button>
              </article>
            ))
          ) : (
            <div className="empty-card">
              Nenhum produto no carrinho ainda. Use a busca ou digite um barcode para adicionar.
            </div>
          )}
        </div>

        <div className="cart-panel__footer">
          <div className="cart-total-strip">
            <span className="cart-summary__label">Valor final</span>
            <strong>R$ {(cart?.total_amount ?? 0).toFixed(2)}</strong>
          </div>
          <button
            className="touch-button touch-button--primary touch-button--wide"
            disabled={checkoutLoading || loading}
            onClick={onCheckout}
            type="button"
          >
            {checkoutLoading ? "Finalizando..." : "Finalizar compra"}
          </button>
        </div>
      </div>
    </section>
  );
}
