import csv
import random
from pathlib import Path

# Config
NUM_PRODUCTS = 150
NUM_PROMOTIONS = 100

CATEGORIES = {
    "Mercearia": ["Arroz", "Feijão", "Macarrão", "Açúcar", "Sal", "Óleo", "Farinha", "Milho", "Ervilha", "Azeite"],
    "Laticínios": ["Leite", "Queijo Mussarela", "Iogurte Natural", "Manteiga", "Requeijão", "Creme de Leite", "Leite Condensado"],
    "Bebidas": ["Café", "Suco de Laranja", "Refrigerante Cola", "Água Mineral", "Cerveja", "Vinho Tinto", "Chá Gelado"],
    "Higiene": ["Shampoo", "Sabonete", "Creme Dental", "Desodorante", "Papel Higiênico", "Fio Dental"],
    "Limpeza": ["Detergente", "Amaciante", "Sabão em Pó", "Desinfetante", "Esponja de Aço", "Água Sanitária"],
    "Padaria": ["Pão de Forma", "Biscoito Recheado", "Bolo de Cenoura", "Pão Francês", "Torrada"],
    "Carnes": ["Acém", "Frango Inteiro", "Linguiça", "Presunto", "Salsicha", "Picanha"],
    "Hortifruti": ["Banana", "Maçã", "Tomate", "Cebola", "Batata", "Alface", "Cenoura"]
}

AISLES = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2", "F1", "F2"]

def generate_barcode(i):
    return f"7891000{100000 + i}"

def generate_catalog():
    products = []
    for i in range(NUM_PRODUCTS):
        cat = random.choice(list(CATEGORIES.keys()))
        item_base = random.choice(CATEGORIES[cat])
        brand = random.choice(["Premium", "Bom Preço", "Saboroso", "Qualidade", "Bio", "Eco", "Nacional", "Fazenda"])
        size = random.choice(["500g", "1kg", "2kg", "1L", "2L", "500ml", "Unidade", "Pacote"])
        
        name = f"{item_base} {brand} {size}"
        price = round(random.uniform(2.5, 95.0), 2)
        barcode = generate_barcode(i)
        aisle = random.choice(AISLES)
        
        products.append({
            "barcode": barcode,
            "name": name,
            "price": price,
            "category": cat,
            "aisle": aisle
        })
    return products

def generate_promotions(products):
    promotions = []
    # Promotion types
    titles = [
        "Oferta Relâmpago", "Leve 2 Pague 1", "Desconto do Dia", 
        "Preço Baixo", "Mega Oferta", "Especial de Final de Semana",
        "Promoção de Verão", "Liquidação Total", "Baixa de Preço",
        "Seleção Especial", "Imperdível", "Só Hoje", "Clube de Descontos"
    ]
    
    selected_products = random.sample(products, min(NUM_PROMOTIONS, len(products)))
    
    for i, product in enumerate(selected_products):
        promo_id = f"promo-gen-{i+1}"
        title = random.choice(titles)
        discount_type = random.choice(["percentage", "fixed"])
        
        # Decide if it has an aisle or not (general promotion)
        aisle = product['aisle'] if random.random() > 0.3 else None
        
        if discount_type == "percentage":
            discount_value = float(random.choice([5, 10, 15, 20, 25, 30, 40, 50]))
            desc = f"Ganhe {int(discount_value)}% de desconto em {product['name']}!"
        else:
            discount_value = float(random.choice([1, 2, 5, 10, 15, 20]))
            if discount_value >= product['price']:
                discount_value = round(product['price'] * 0.25, 2)
            desc = f"Desconto fixo de R$ {discount_value:.2f} no produto {product['name']}."

        promotions.append({
            "id": promo_id,
            "title": f"{title}: {product['name']}",
            "description": desc,
            "product_barcode": product['barcode'],
            "discount_type": discount_type,
            "discount_value": discount_value,
            "aisle": aisle
        })
    return promotions

def main():
    root = Path(__file__).resolve().parent.parent
    catalog_path = root / "mock_supermercado" / "catalog.csv"
    promotions_path = root / "mock_supermercado" / "promotions.csv"
    data_py_path = root / "mock_supermercado" / "data.py"
    
    products = generate_catalog()
    
    # Write Catalog CSV
    with open(catalog_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["barcode", "name", "price", "category", "aisle"])
        writer.writeheader()
        writer.writerows(products)
    
    # Generate Promotions
    promotions = generate_promotions(products)
    
    # Write Promotions CSV
    with open(promotions_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "description", "product_barcode", "discount_type", "discount_value", "aisle"])
        writer.writeheader()
        writer.writerows(promotions)
    
    # Write data.py
    with open(data_py_path, "w", encoding="utf-8") as f:
        f.write("from pathlib import Path\n\n\n")
        f.write('CATALOG_CSV_PATH = Path(__file__).resolve().parent / "catalog.csv"\n')
        f.write('PROMOTIONS_CSV_PATH = Path(__file__).resolve().parent / "promotions.csv"\n')

    print(f"Generated {len(products)} products and {len(promotions)} promotions in CSV format.")

if __name__ == "__main__":
    main()
