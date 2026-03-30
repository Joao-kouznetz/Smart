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

## Testes

```bash
pytest
```
