"""
Smart Cart 360° — Script de População do Histórico de Compras
==============================================================

Gera transações sintéticas de compras baseadas em 8 personas com
perfis de consumo distintos, simulando comportamentos reais de
consumidores em um supermercado brasileiro.

Personas:
    1. Família Grande      — compra semanal volumosa
    2. Universitário       — compra rápida, snacks e bebidas
    3. Fitness             — dieta proteica, frutas e verduras
    4. Idoso(a)            — compra frequente e pequena
    5. Churrasqueiro       — carnes e bebidas
    6. Dona(o) de Casa     — limpeza e higiene
    7. Cozinheiro Gourmet  — ingredientes variados
    8. Compra de Emergência — 1-3 itens aleatórios

Uso:
    python scripts/populate_purchase_history.py --num-purchases 100
    python scripts/populate_purchase_history.py --num-purchases 500 --clear

Autores: [Seu nome aqui]
Projeto: Smart Cart 360° — TCC Insper 2026
"""

import argparse
import csv
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. CAMINHOS
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent.parent / "servidor_central" / "smart_cart.db"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "mock_supermercado" / "catalog.csv"


# ---------------------------------------------------------------------------
# 2. CATÁLOGO
# ---------------------------------------------------------------------------

def load_catalog(catalog_path: Path) -> list[dict]:
    """Carrega o catálogo de produtos do CSV."""
    products = []
    with open(catalog_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["price"] = float(row["price"])
            products.append(row)
    return products


def get_products_by_category(catalog: list[dict]) -> dict[str, list[dict]]:
    """Agrupa produtos por categoria."""
    by_cat: dict[str, list[dict]] = {}
    for p in catalog:
        cat = p.get("category", "Outros")
        by_cat.setdefault(cat, []).append(p)
    return by_cat


# ---------------------------------------------------------------------------
# 3. PERSONAS
# ---------------------------------------------------------------------------
# Cada persona define:
#   - name: identificador da persona
#   - weight: probabilidade relativa de ser escolhida (soma não precisa ser 1)
#   - high_freq: categorias que SEMPRE aparecem na compra (1-3 itens cada)
#   - occasional: categorias com 40% de chance de aparecer (1-2 itens cada)
#   - cart_size: (min, max) de itens totais na cesta
# ---------------------------------------------------------------------------

PERSONAS = [
    {
        "name": "familia_grande",
        "weight": 25,
        "high_freq": ["Mercearia", "Carnes", "Laticínios", "Limpeza"],
        "occasional": ["Hortifruti", "Padaria", "Higiene"],
        "cart_size": (10, 18),
    },
    {
        "name": "universitario",
        "weight": 15,
        "high_freq": ["Padaria", "Bebidas", "Mercearia"],
        "occasional": ["Higiene", "Laticínios"],
        "cart_size": (3, 7),
    },
    {
        "name": "fitness",
        "weight": 10,
        "high_freq": ["Carnes", "Hortifruti", "Laticínios"],
        "occasional": ["Bebidas", "Higiene"],
        "cart_size": (5, 10),
    },
    {
        "name": "idoso",
        "weight": 12,
        "high_freq": ["Padaria", "Laticínios", "Mercearia"],
        "occasional": ["Higiene", "Limpeza", "Hortifruti"],
        "cart_size": (3, 6),
    },
    {
        "name": "churrasqueiro",
        "weight": 10,
        "high_freq": ["Carnes", "Bebidas"],
        "occasional": ["Mercearia", "Hortifruti", "Padaria"],
        "cart_size": (4, 8),
    },
    {
        "name": "dona_de_casa",
        "weight": 12,
        "high_freq": ["Limpeza", "Higiene"],
        "occasional": ["Mercearia", "Padaria", "Laticínios"],
        "cart_size": (5, 10),
    },
    {
        "name": "cozinheiro_gourmet",
        "weight": 8,
        "high_freq": ["Mercearia", "Hortifruti", "Laticínios", "Carnes"],
        "occasional": ["Bebidas", "Padaria"],
        "cart_size": (8, 15),
    },
    {
        "name": "compra_emergencia",
        "weight": 8,
        "high_freq": [],
        "occasional": [],
        "cart_size": (1, 3),
    },
]


# ---------------------------------------------------------------------------
# 4. GERAÇÃO DE UMA COMPRA
# ---------------------------------------------------------------------------

def generate_purchase(
    persona: dict,
    catalog: list[dict],
    by_category: dict[str, list[dict]],
    purchase_date: str,
) -> tuple[dict, list[dict]]:
    """
    Gera uma compra sintética baseada no perfil de uma persona.

    Fluxo:
        1. Para cada categoria de alta frequência, seleciona 1-3 produtos
        2. Para cada categoria ocasional, 40% de chance de selecionar 1-2 produtos
        3. Se a cesta ainda não atingiu o tamanho mínimo, complementa
           com produtos aleatórios
        4. Se ultrapassou o máximo, corta aleatoriamente
        5. Atribui quantidade 1-3 para cada item
    """
    selected: dict[str, dict] = {}  # barcode → product
    min_items, max_items = persona["cart_size"]

    # --- Passo 1: Categorias de alta frequência (sempre presentes) ---
    for cat in persona["high_freq"]:
        if cat not in by_category:
            continue
        count = random.randint(1, 3)
        available = by_category[cat]
        chosen = random.sample(available, min(count, len(available)))
        for product in chosen:
            selected[product["barcode"]] = product

    # --- Passo 2: Categorias ocasionais (40% de chance) ---
    for cat in persona["occasional"]:
        if random.random() > 0.40:
            continue
        if cat not in by_category:
            continue
        count = random.randint(1, 2)
        available = by_category[cat]
        chosen = random.sample(available, min(count, len(available)))
        for product in chosen:
            selected[product["barcode"]] = product

    # --- Passo 3: Complementar se abaixo do mínimo ---
    while len(selected) < min_items:
        extra = random.choice(catalog)
        selected[extra["barcode"]] = extra

    # --- Passo 4: Cortar se acima do máximo ---
    if len(selected) > max_items:
        barcodes_to_keep = random.sample(list(selected.keys()), max_items)
        selected = {bc: selected[bc] for bc in barcodes_to_keep}

    # --- Passo 5: Montar itens com quantidades ---
    items = []
    total_amount = 0.0

    for barcode, product in selected.items():
        quantity = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
        subtotal = product["price"] * quantity
        total_amount += subtotal

        items.append({
            "barcode": barcode,
            "name": product["name"],
            "price": product["price"],
            "quantity": quantity,
            "category": product.get("category", ""),
            "aisle": product.get("aisle", ""),
        })

    header = {
        "persona": persona["name"],
        "purchase_date": purchase_date,
        "total_amount": round(total_amount, 2),
        "total_items": sum(i["quantity"] for i in items),
    }

    return header, items


# ---------------------------------------------------------------------------
# 5. GERAÇÃO DE TODAS AS COMPRAS
# ---------------------------------------------------------------------------

def pick_persona() -> dict:
    """Escolhe uma persona aleatoriamente com base nos pesos."""
    weights = [p["weight"] for p in PERSONAS]
    return random.choices(PERSONAS, weights=weights, k=1)[0]


def generate_all_purchases(
    catalog: list[dict],
    num_purchases: int,
) -> list[tuple[dict, list[dict]]]:
    """Gera N compras distribuídas nos últimos 90 dias."""
    by_category = get_products_by_category(catalog)
    purchases = []

    now = datetime.now(timezone.utc)

    for _ in range(num_purchases):
        persona = pick_persona()

        # Data aleatória nos últimos 90 dias, horário comercial
        days_ago = random.randint(0, 90)
        hours_offset = random.randint(8, 22)
        purchase_date = (
            now - timedelta(days=days_ago) + timedelta(hours=hours_offset)
        ).isoformat()

        header, items = generate_purchase(persona, catalog, by_category, purchase_date)
        purchases.append((header, items))

    return purchases


# ---------------------------------------------------------------------------
# 6. PERSISTÊNCIA NO SQLITE
# ---------------------------------------------------------------------------

def clear_history(conn: sqlite3.Connection) -> None:
    """Limpa todo o histórico existente."""
    conn.execute("DELETE FROM purchase_items")
    conn.execute("DELETE FROM purchase_history")
    conn.commit()


def save_purchases(
    conn: sqlite3.Connection,
    purchases: list[tuple[dict, list[dict]]],
) -> int:
    """Salva todas as compras no banco. Retorna total inserido."""
    count = 0

    for header, items in purchases:
        cursor = conn.execute(
            """
            INSERT INTO purchase_history (persona, purchase_date, total_amount, total_items)
            VALUES (?, ?, ?, ?)
            """,
            (header["persona"], header["purchase_date"],
             header["total_amount"], header["total_items"]),
        )
        purchase_id = cursor.lastrowid

        for item in items:
            conn.execute(
                """
                INSERT INTO purchase_items
                    (purchase_id, barcode, name, price, quantity, category, aisle)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    purchase_id,
                    item["barcode"],
                    item["name"],
                    item["price"],
                    item["quantity"],
                    item["category"],
                    item["aisle"],
                ),
            )
        count += 1

    conn.commit()
    return count


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Popula o histórico de compras do Smart Cart com dados sintéticos."
    )
    parser.add_argument(
        "--num-purchases",
        type=int,
        default=100,
        help="Número de compras a gerar (default: 100)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Limpar histórico existente antes de popular",
    )
    args = parser.parse_args()

    # --- Carregar catálogo ---
    print(f"Carregando catalogo de {CATALOG_PATH}...")
    catalog = load_catalog(CATALOG_PATH)
    print(f"  -> {len(catalog)} produtos encontrados")

    # --- Conectar ao banco ---
    print(f"Conectando ao banco {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    # --- Limpar se solicitado ---
    if args.clear:
        print("Limpando historico existente...")
        clear_history(conn)

    # --- Gerar e salvar ---
    print(f"Gerando {args.num_purchases} compras sinteticas com 8 personas...")
    purchases = generate_all_purchases(catalog, args.num_purchases)

    print("Salvando no banco de dados...")
    saved = save_purchases(conn, purchases)

    # --- Estatísticas ---
    total_items = conn.execute("SELECT COUNT(*) FROM purchase_items").fetchone()[0]
    total_purchases = conn.execute("SELECT COUNT(*) FROM purchase_history").fetchone()[0]

    # Contagem por persona
    persona_counts = conn.execute(
        "SELECT persona, COUNT(*) as cnt FROM purchase_history GROUP BY persona ORDER BY cnt DESC"
    ).fetchall()

    print(f"\n{'='*50}")
    print(f"  RESUMO DA POPULACAO")
    print(f"{'='*50}")
    print(f"  Compras inseridas agora:    {saved}")
    print(f"  Total de compras no banco:  {total_purchases}")
    print(f"  Total de itens no banco:    {total_items}")
    print(f"  Media de itens por compra:  {total_items / max(total_purchases, 1):.1f}")
    print(f"\n  Compras por persona:")
    for row in persona_counts:
        print(f"    {row[0]:.<30} {row[1]:>4} compras")
    print(f"{'='*50}")

    conn.close()
    print("Pronto!")


if __name__ == "__main__":
    main()