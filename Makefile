FASTAPI ?= fastapi
MOCK_PORT ?= 8001
SERVER_PORT ?= 8000
MOCK_URL ?= http://127.0.0.1:$(MOCK_PORT)
NPM ?= npm

.PHONY: dev-servidor dev-mock dev-front build-front

dev-servidor:
	BASE_SUPERMARKET_API_URL=$(MOCK_URL) $(FASTAPI) dev servidor_central/main.py --port $(SERVER_PORT)

dev-mock:
	$(FASTAPI) dev mock_supermercado/main.py --port $(MOCK_PORT)

dev-front:
	cd front && $(NPM) run dev

build-front:
	cd front && $(NPM) run build
