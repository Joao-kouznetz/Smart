# Mock Supermercado

API FastAPI separada que simula o sistema externo do supermercado.

O catalogo de produtos fica em `mock_supermercado/catalog.csv` e pode ser editado manualmente.

## Executar

```bash
fastapi dev mock_supermercado/main.py --port 8001
```

## Simular compras no Smart Cart

As personas ficam em `mock_supermercado/simulation/personas.py` e o layout virtual
fica em `mock_supermercado/simulation/layout.py`.

```bash
python3 scripts/populate_simulated_purchases.py 50 --seed 42
```

Por padrao o script usa o banco configurado por `SMART_CART_DB_PATH`, ou
`servidor_central/smart_cart.db` quando a variavel nao estiver definida.
Use `--clear-existing-data` se quiser apagar os dados simulados antes de gravar
um novo lote.
