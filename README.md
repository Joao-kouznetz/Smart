# Smart

Monorepo local do prototipo Smart Cart com tres partes separadas:

- `servidor_central`: API principal do Smart Cart usando SQLite nativo (`sqlite3`) e sem ORM.
- `mock_supermercado`: API simulada do sistema externo do supermercado.
- `front`: SPA touch-first em React + Vite + TypeScript para a tela do carrinho.

## Estrutura

```text
.
├── front/
├── mock_supermercado/
└── servidor_central/
```

## Executar o mock do supermercado

```bash
fastapi dev mock_supermercado/main.py --port 8001
```

## Executar o servidor central

```bash
BASE_SUPERMARKET_API_URL=http://127.0.0.1:8001 fastapi dev servidor_central/main.py --port 8000
```

## Executar o frontend em desenvolvimento

```bash
cd front
npm install --cache /tmp/smart-cart-npm-cache
npm run dev
```

Durante o desenvolvimento, o Vite faz proxy das rotas do backend para `http://127.0.0.1:8000`.

## Build do frontend

```bash
cd front
npm run build
```

Depois do build, o `servidor_central` serve a interface em:

```text
http://127.0.0.1:8000/app
```

## Comandos prontos

```bash
make dev-mock
make dev-servidor
make dev-front
make build-front
```

Ou, se preferir:

```bash
sh scripts/dev_mock_supermercado.sh
sh scripts/dev_servidor_central.sh
```

## Configuracao

- `SMART_CART_DB_PATH`: caminho opcional do arquivo SQLite do `servidor_central`.
- `BASE_SUPERMARKET_API_URL`: URL base da API externa consumida pelo `servidor_central`.
- `FRONTEND_DIST_PATH`: caminho opcional para o build do frontend servido em `/app`.

## Device ID

- O frontend usa o `device_id` persistido no dispositivo como `cart_id`.
- Precedencia: `VITE_DEVICE_ID` -> `?deviceId=...` -> `localStorage` -> geracao automatica.

## Checkout

- `POST /cart/{cart_id}/checkout`: finaliza a compra limpando todos os itens do carrinho.
- A tabela `carts` nao usa mais campo `status`.

## Grafo de localizacao

Recrie o grafo quantas vezes precisar a partir dos eventos salvos no SQLite:

```bash
make build-location-graph ARGS="--start-at 2026-04-01T00:00:00+00:00 --temporal-decay --half-life-days 30"
```

Se estiver usando a `.venv` local, rode com `PYTHON=.venv/bin/python`. Se `--start-at` for omitido, o treino usa todos os eventos disponiveis. O JSON gerado fica no cache configurado por `SMART_CART_LOCATION_GRAPH_PATH` ou em `servidor_central/location_graph.json`.

A tela de demonstracao/debug do grafo fica em:

```text
http://127.0.0.1:8000/app/graph
```

Para ver o grafo funcionando, rode a partir da raiz do projeto:

cd /Users/joaobresser/Documents/Insper/PFE/Smart
Instale as dependências Python na venv:
.venv/bin/pip install -r requirements.txt
Instale as dependências do frontend:
cd front
npm install
cd ..
Gere mais dados simulados para o grafo ter arestas suficientes:
.venv/bin/python scripts/populate_simulated_purchases.py 300 --seed 42
O número 300 é importante porque a regra atual descarta arestas com menos de 15 ocorrências. Com poucos carrinhos, o grafo pode aparecer só com nós e sem ligações.
Se quiser recriar os dados do zero, adicione `--clear-existing-data`.

Recrie o grafo:
make PYTHON=.venv/bin/python build-location-graph ARGS="--temporal-decay --half-life-days 30"
Se quiser treinar só a partir de uma data específica:

make PYTHON=.venv/bin/python build-location-graph ARGS="--start-at 2026-04-01T00:00:00+00:00 --temporal-decay --half-life-days 30"
Gere o build do frontend:
cd front
npm run build
cd ..
Suba o servidor central:
BASE_SUPERMARKET_API_URL=<http://127.0.0.1:8001> .venv/bin/uvicorn servidor_central.main:app --port 8000
Abra no navegador:
<http://127.0.0.1:8000/app/graph>
Na tela, você consegue buscar produto por nome/barcode, destacar ele no grafo e clicar em “Recriar grafo”.

Para verificar rapidamente se o grafo tem arestas:

curl <http://127.0.0.1:8000/location-graph>

## Testes

```bash
pytest
```
