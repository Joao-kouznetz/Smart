import type { Promotion } from "../lib/types";

interface PromotionRailProps {
  title: string;
  subtitle: string;
  promotions: Promotion[];
  loading?: boolean;
  emptyLabel: string;
}

function formatDiscount(promotion: Promotion): string {
  if (promotion.discount_type === "percentage" && promotion.discount_value != null) {
    return `${promotion.discount_value}% OFF`;
  }

  if (promotion.discount_type === "fixed" && promotion.discount_value != null) {
    return `R$ ${promotion.discount_value.toFixed(2)} OFF`;
  }

  return "Oferta ativa";
}

export function PromotionRail({
  title,
  subtitle,
  promotions,
  loading = false,
  emptyLabel,
}: PromotionRailProps) {
  return (
    <section className="panel promotion-panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">{title}</p>
          <h2>{subtitle}</h2>
        </div>
        <span className="panel__badge">Promocoes</span>
      </div>

      <div className="promotion-rail" role="list" aria-label={subtitle}>
        {loading ? (
          <div className="empty-card">Carregando promocoes...</div>
        ) : promotions.length === 0 ? (
          <div className="empty-card">{emptyLabel}</div>
        ) : (
          promotions.map((promotion) => (
            <article className="promotion-card" key={promotion.id} role="listitem">
              <span className="promotion-card__tag">{formatDiscount(promotion)}</span>
              <h3>{promotion.title}</h3>
              <p>{promotion.description ?? "Oferta pronta para ser exibida no carrinho."}</p>
              <div className="promotion-card__meta">
                {promotion.aisle ? <span>Corredor {promotion.aisle}</span> : null}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
