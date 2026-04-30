"""Personas editaveis para geracao de compras simuladas."""

PERSONAS = [
    {
        "name": "Familia compra semanal",
        "products": [
            {"barcode": "7891000100054", "name": "Feijão Nacional Pacote"},
            {"barcode": "7891000100039", "name": "Macarrão Bom Preço Pacote"},
            {"barcode": "7891000100017", "name": "Óleo Bom Preço 500ml"},
            {"barcode": "7891000100007", "name": "Leite Saboroso Unidade"},
            {"barcode": "7891000100004", "name": "Batata Fazenda 500g"},
            {"barcode": "7891000100030", "name": "Cenoura Saboroso Pacote"},
            {"barcode": "7891000100057", "name": "Frango Inteiro Saboroso 1kg"},
        ],
    },
    {
        "name": "Cafe da manha rapido",
        "products": [
            {"barcode": "7891000100020", "name": "Pão de Forma Bom Preço 1L"},
            {"barcode": "7891000100022", "name": "Manteiga Fazenda 1L"},
            {"barcode": "7891000100082", "name": "Café Bom Preço 1L"},
            {"barcode": "7891000100009", "name": "Torrada Bom Preço 2kg"},
            {"barcode": "7891000100053", "name": "Suco de Laranja Premium 2L"},
        ],
    },
    {
        "name": "Churrasco fim de semana",
        "products": [
            {"barcode": "7891000100010", "name": "Picanha Eco Pacote"},
            {"barcode": "7891000100018", "name": "Linguiça Nacional 500ml"},
            {"barcode": "7891000100003", "name": "Cerveja Fazenda 2L"},
            {"barcode": "7891000100059", "name": "Vinho Tinto Bom Preço 2L"},
            {"barcode": "7891000100026", "name": "Água Mineral Saboroso 500g"},
        ],
    },
    {
        "name": "Limpeza e higiene",
        "products": [
            {"barcode": "7891000100013", "name": "Detergente Eco 1L"},
            {"barcode": "7891000100015", "name": "Amaciante Bio 2kg"},
            {"barcode": "7891000100046", "name": "Sabão em Pó Saboroso 1kg"},
            {"barcode": "7891000100056", "name": "Papel Higiênico Premium 2kg"},
            {"barcode": "7891000100048", "name": "Sabonete Saboroso 1L"},
            {"barcode": "7891000100034", "name": "Shampoo Nacional 500ml"},
        ],
    },
    {
        "name": "Lanche de crianca",
        "products": [
            {"barcode": "7891000100043", "name": "Biscoito Recheado Premium Unidade"},
            {"barcode": "7891000100068", "name": "Biscoito Recheado Eco 1L"},
            {"barcode": "7891000100028", "name": "Leite Condensado Bom Preço 1kg"},
            {"barcode": "7891000100014", "name": "Pão Francês Bom Preço 500ml"},
            {"barcode": "7891000100069", "name": "Refrigerante Cola Saboroso 1L"},
        ],
    },
]

PERSONA_PROPORTIONS = [0.35, 0.2, 0.15, 0.15, 0.15]
