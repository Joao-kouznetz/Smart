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

Por padrao, os tempos entre produtos usam `--travel-time-distribution fixed`,
mantendo um tempo deterministico por rota: distancia dividida pela velocidade de
caminhada simulada mais o tempo de pegar o item na prateleira. Para testar
remocao de outliers, use:

```bash
python3 scripts/populate_simulated_purchases.py 300 --seed 42 --travel-time-distribution normal
python3 scripts/populate_simulated_purchases.py 300 --seed 42 --travel-time-distribution right-tail
python3 scripts/populate_simulated_purchases.py 300 --seed 42 --travel-time-distribution bimodal
```

`normal` varia ao redor do tempo esperado pela distancia, `right-tail` cria um
pico com cauda longa para a direita, e `bimodal` mistura uma normal estreita com
pico em 0.3s com uma segunda distribuicao de cauda longa. No `bimodal`, o grupo
rapido recebe menos massa para o pico estreito nao dominar visualmente o segundo
pico.

Por padrao o script usa o banco configurado por `SMART_CART_DB_PATH`, ou
`servidor_central/smart_cart.db` quando a variavel nao estiver definida.
Use `--clear-existing-data` se quiser apagar os dados simulados antes de gravar
um novo lote.
