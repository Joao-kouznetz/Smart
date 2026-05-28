import csv
from pathlib import Path

ROOT = Path('/Users/joaobresser/Documents/Insper/PFE/Smart')
CATALOG_PATH = ROOT / 'mock_supermercado/catalog.csv'
PERSONAS_PATH = ROOT / 'mock_supermercado/simulation/personas.py'
PROMO_PATH = ROOT / 'mock_supermercado/promotions.csv'

def normalize_name(name):
    return name.strip().lower()

def dedup():
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    seen_names = {}
    kept_rows = []
    barcode_map = {}

    for row in rows:
        name_key = normalize_name(row['name'])
        if name_key not in seen_names:
            seen_names[name_key] = row['barcode']
            kept_rows.append(row)
        else:
            barcode_map[row['barcode']] = seen_names[name_key]

    with open(CATALOG_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(kept_rows)

    # Update personas
    with open(PERSONAS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    for old_bc, new_bc in barcode_map.items():
        content = content.replace(f'"{old_bc}"', f'"{new_bc}"')

    with open(PERSONAS_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    # Update promotions
    with open(PROMO_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        promos = list(reader)
        
    for p in promos:
        if p['product_barcode'] in barcode_map:
            p['product_barcode'] = barcode_map[p['product_barcode']]
            
    with open(PROMO_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=promos[0].keys())
        writer.writeheader()
        writer.writerows(promos)

    print(f"Kept {len(kept_rows)} items. Replaced {len(barcode_map)} duplicates.")

if __name__ == '__main__':
    dedup()
