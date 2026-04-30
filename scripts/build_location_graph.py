import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from servidor_central.algorithms.location_graph import rebuild_location_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recria o grafo de localizacao do Smart Cart a partir do SQLite."
    )
    parser.add_argument(
        "--start-at",
        default=None,
        help="Data inicial ISO 8601 para treinar o grafo. Se omitida, usa todos os dados.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Caminho opcional do SQLite. Se omitido, usa SMART_CART_DB_PATH ou o padrao.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Caminho opcional do JSON do grafo. Se omitido, usa o cache padrao.",
    )
    parser.add_argument(
        "--temporal-decay",
        action="store_true",
        help="Ativa decaimento temporal para dados antigos valerem menos.",
    )
    parser.add_argument(
        "--half-life-days",
        type=float,
        default=30.0,
        help="Meia-vida em dias quando o decaimento temporal esta ativo.",
    )
    parser.add_argument(
        "--decay-min-weight",
        type=float,
        default=0.01,
        help="Peso minimo para uma transicao continuar valendo no treino.",
    )

    args = parser.parse_args()
    graph = rebuild_location_graph(
        db_path=args.db_path,
        output_path=args.output,
        start_at=args.start_at,
        temporal_decay=args.temporal_decay,
        half_life_days=args.half_life_days,
        decay_min_weight=args.decay_min_weight,
    )
    meta = graph["meta"]
    print(
        "Grafo recriado: "
        f"{meta['node_count']} nos, "
        f"{meta['edge_count']} arestas, "
        f"{meta['valid_transition_count']} transicoes validas, "
        f"cache={meta['cache_path']}"
    )
    if meta.get("dependency_warning"):
        print(f"Aviso: {meta['dependency_warning']}")


if __name__ == "__main__":
    main()
