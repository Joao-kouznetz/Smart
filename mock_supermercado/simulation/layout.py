"""Layout virtual editavel do supermercado.

Cada chave representa um corredor/estante. Dentro do corredor, cada produto
declara a distancia ate os dois corredores laterais que conectam as estantes.
"""

AISLE_GAP_METERS = 4.0

SUPERMARKET_LAYOUT = {
    "A1": [
        {
            "barcode": "7891000100008",
            "name": "Presunto Bio 1kg",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100022",
            "name": "Manteiga Fazenda 1L",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100043",
            "name": "Biscoito Recheado Premium Unidade",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100053",
            "name": "Suco de Laranja Premium 2L",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100075",
            "name": "Azeite Premium Unidade",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "A2": [
        {
            "barcode": "7891000100005",
            "name": "Milho Fazenda 2kg",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100014",
            "name": "Pão Francês Bom Preço 500ml",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100054",
            "name": "Feijão Nacional Pacote",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100055",
            "name": "Queijo Mussarela Qualidade Pacote",
            "dist_lateral_1_m": 13.0,
            "dist_lateral_2_m": 7.0,
        },
        {
            "barcode": "7891000100059",
            "name": "Vinho Tinto Bom Preço 2L",
            "dist_lateral_1_m": 17.0,
            "dist_lateral_2_m": 3.0,
        },
    ],
    "B1": [
        {
            "barcode": "7891000100017",
            "name": "Óleo Bom Preço 500ml",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100037",
            "name": "Farinha Nacional 1kg",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100039",
            "name": "Macarrão Bom Preço Pacote",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100045",
            "name": "Esponja de Aço Qualidade 2kg",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100076",
            "name": "Acém Fazenda 500ml",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "B2": [
        {
            "barcode": "7891000100009",
            "name": "Torrada Bom Preço 2kg",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100012",
            "name": "Tomate Fazenda 2kg",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100013",
            "name": "Detergente Eco 1L",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100030",
            "name": "Cenoura Saboroso Pacote",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100056",
            "name": "Papel Higiênico Premium 2kg",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "C1": [
        {
            "barcode": "7891000100003",
            "name": "Cerveja Fazenda 2L",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100025",
            "name": "Esponja de Aço Qualidade 1kg",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100046",
            "name": "Sabão em Pó Saboroso 1kg",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100047",
            "name": "Creme de Leite Nacional Unidade",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100082",
            "name": "Café Bom Preço 1L",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "C2": [
        {
            "barcode": "7891000100026",
            "name": "Água Mineral Saboroso 500g",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100028",
            "name": "Leite Condensado Bom Preço 1kg",
            "dist_lateral_1_m": 8.0,
            "dist_lateral_2_m": 12.0,
        },
        {
            "barcode": "7891000100029",
            "name": "Salsicha Eco 500g",
            "dist_lateral_1_m": 12.0,
            "dist_lateral_2_m": 8.0,
        },
        {
            "barcode": "7891000100048",
            "name": "Sabonete Saboroso 1L",
            "dist_lateral_1_m": 16.0,
            "dist_lateral_2_m": 4.0,
        },
    ],
    "D1": [
        {
            "barcode": "7891000100002",
            "name": "Fio Dental Nacional 500g",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100011",
            "name": "Sabão em Pó Nacional 2L",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100015",
            "name": "Amaciante Bio 2kg",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100051",
            "name": "Acém Bom Preço 1L",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100069",
            "name": "Refrigerante Cola Saboroso 1L",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "D2": [
        {
            "barcode": "7891000100004",
            "name": "Batata Fazenda 500g",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100006",
            "name": "Shampoo Nacional 2kg",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100021",
            "name": "Manteiga Saboroso 2kg",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100031",
            "name": "Pão Francês Premium 2kg",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100049",
            "name": "Sabão em Pó Eco Unidade",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "E1": [
        {
            "barcode": "7891000100007",
            "name": "Leite Saboroso Unidade",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100016",
            "name": "Batata Bio Pacote",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100034",
            "name": "Shampoo Nacional 500ml",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100041",
            "name": "Vinho Tinto Nacional 2L",
            "dist_lateral_1_m": 13.0,
            "dist_lateral_2_m": 7.0,
        },
        {
            "barcode": "7891000100068",
            "name": "Biscoito Recheado Eco 1L",
            "dist_lateral_1_m": 17.0,
            "dist_lateral_2_m": 3.0,
        },
    ],
    "E2": [
        {
            "barcode": "7891000100000",
            "name": "Açúcar Eco 2L",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100001",
            "name": "Frango Inteiro Premium 500ml",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100018",
            "name": "Linguiça Nacional 500ml",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100027",
            "name": "Torrada Bom Preço 2L",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100078",
            "name": "Biscoito Recheado Qualidade 500g",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "F1": [
        {
            "barcode": "7891000100020",
            "name": "Pão de Forma Bom Preço 1L",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100035",
            "name": "Desinfetante Bom Preço 1kg",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100057",
            "name": "Frango Inteiro Saboroso 1kg",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100064",
            "name": "Pão Francês Eco 500ml",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100067",
            "name": "Fio Dental Bio 1kg",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "F2": [
        {
            "barcode": "7891000100010",
            "name": "Picanha Eco Pacote",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100023",
            "name": "Presunto Fazenda 500ml",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100033",
            "name": "Óleo Bom Preço 2L",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100050",
            "name": "Feijão Bom Preço 1L",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100079",
            "name": "Queijo Mussarela Qualidade Unidade",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
}
