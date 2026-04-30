import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mock_supermercado.simulation.layout import AISLE_GAP_METERS, SUPERMARKET_LAYOUT
from mock_supermercado.simulation.personas import PERSONA_PROPORTIONS, PERSONAS
from mock_supermercado.simulation.purchase_simulator import populate_simulated_purchases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Popula o SQLite do Smart Cart com compras simuladas."
    )
    parser.add_argument("people_count", type=int, help="Quantidade de pessoas/carrinhos simulados.")
    parser.add_argument("--seed", type=int, default=None, help="Seed para resultados reproduziveis.")
    parser.add_argument(
        "--cart-id-prefix",
        default="sim-cart",
        help="Prefixo usado nos IDs de carrinho gerados.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Caminho do SQLite. Se omitido, usa SMART_CART_DB_PATH ou o padrao do servidor.",
    )
    parser.add_argument(
        "--start-at",
        default=None,
        help="Horario base ISO 8601. Ex: 2026-04-29T09:00:00+00:00.",
    )

    args = parser.parse_args()
    start_at = datetime.fromisoformat(args.start_at) if args.start_at else None
    result = populate_simulated_purchases(
        people_count=args.people_count,
        supermarket_layout=SUPERMARKET_LAYOUT,
        personas=PERSONAS,
        persona_proportions=PERSONA_PROPORTIONS,
        db_path=args.db_path,
        cart_id_prefix=args.cart_id_prefix,
        seed=args.seed,
        start_at=start_at,
        aisle_gap_m=AISLE_GAP_METERS,
    )

    print(
        "Simulacao concluida: "
        f"{result.people_count} carrinhos, "
        f"{result.interaction_count} eventos, "
        f"primeiro={result.first_event_at}, ultimo={result.last_event_at}"
    )


if __name__ == "__main__":
    main()
