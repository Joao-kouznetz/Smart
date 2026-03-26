# Servidor Central

API FastAPI principal do Smart Cart.

## Executar

```bash
BASE_SUPERMARKET_API_URL=http://127.0.0.1:8001 fastapi dev servidor_central/main.py --port 8000
```

## Endpoint adicional

- `POST /cart/{cart_id}/checkout`: remove todos os itens do carrinho e retorna o carrinho vazio.
