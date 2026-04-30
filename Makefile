FASTAPI ?= fastapi
MOCK_PORT ?= 8001
SERVER_PORT ?= 8000
MOCK_URL ?= http://127.0.0.1:$(MOCK_PORT)
NPM ?= npm
PYTHON ?= python3

.PHONY: dev-servidor dev-mock dev-front build-front build-location-graph

dev-servidor:
	@trap 'kill 0' EXIT; \
	cd front && $(NPM) run build && $(NPM) run dev -- --host 0.0.0.0 & \
	BASE_SUPERMARKET_API_URL=$(MOCK_URL) $(FASTAPI) dev servidor_central/main.py --port $(SERVER_PORT) & \
	wait

dev-mock:
	$(FASTAPI) dev mock_supermercado/main.py --port $(MOCK_PORT)

dev-front:
	cd front && $(NPM) run dev

build-front:
	cd front && $(NPM) run build

build-location-graph:
	$(PYTHON) scripts/build_location_graph.py $(ARGS)
