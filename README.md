# Smart

Monorepo local do prototipo Smart Cart com tres partes separadas:

- `servidor_central`: API principal do Smart Cart usando SQLite nativo (`sqlite3`) e sem ORM.
- `mock_supermercado`: API simulada do sistema externo do supermercado.
- `front`: pasta reservada para o frontend.

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

## Comandos prontos

```bash
make dev-mock
make dev-servidor
```

Ou, se preferir:

```bash
sh scripts/dev_mock_supermercado.sh
sh scripts/dev_servidor_central.sh
```

## Configuracao

- `SMART_CART_DB_PATH`: caminho opcional do arquivo SQLite do `servidor_central`.
- `BASE_SUPERMARKET_API_URL`: URL base da API externa consumida pelo `servidor_central`.

## Testes

```bash
pytest
```
