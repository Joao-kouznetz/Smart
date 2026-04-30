"""Layout virtual editavel do supermercado.

Cada chave representa um corredor/estante. Dentro do corredor, cada produto
declara a distancia ate os dois corredores laterais que conectam as estantes.
"""

AISLE_GAP_METERS = 4.0

SUPERMARKET_LAYOUT = {
    "A1": [
        {
            "barcode": "7891000100008",
            "name": "Presunto",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100022",
            "name": "Manteiga sem sal",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100043",
            "name": "Biscoito Recheado",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100053",
            "name": "Suco de Laranja",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100075",
            "name": "Azeite Seleção",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "A2": [
        {
            "barcode": "7891000100005",
            "name": "Milho",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100014",
            "name": "Pão Francês",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100054",
            "name": "Feijão",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100055",
            "name": "Queijo Mussarela",
            "dist_lateral_1_m": 13.0,
            "dist_lateral_2_m": 7.0,
        },
        {
            "barcode": "7891000100059",
            "name": "Vinho Tinto",
            "dist_lateral_1_m": 17.0,
            "dist_lateral_2_m": 3.0,
        },
    ],
    "B1": [
        {
            "barcode": "7891000100017",
            "name": "Óleo de girasol",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100037",
            "name": "Farinha",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100039",
            "name": "Macarrão",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100045",
            "name": "Esponja de Aço",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100076",
            "name": "Acém",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "B2": [
        {
            "barcode": "7891000100009",
            "name": "Torrada Tradicional",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100012",
            "name": "Tomate",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100013",
            "name": "Detergente",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100030",
            "name": "Cenoura Organica",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100056",
            "name": "Papel Higiênico",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "C1": [
        {
            "barcode": "7891000100003",
            "name": "Cerveja Artesanal",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100025",
            "name": "Esponja de Aço",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100046",
            "name": "Sabão em Pó ",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100047",
            "name": "Creme de Leite",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100082",
            "name": "Café",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "C2": [
        {
            "barcode": "7891000100026",
            "name": "Água Mineral",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100028",
            "name": "Leite Condensado",
            "dist_lateral_1_m": 8.0,
            "dist_lateral_2_m": 12.0,
        },
        {
            "barcode": "7891000100029",
            "name": "Salsicha",
            "dist_lateral_1_m": 12.0,
            "dist_lateral_2_m": 8.0,
        },
        {
            "barcode": "7891000100048",
            "name": "Sabonete ",
            "dist_lateral_1_m": 16.0,
            "dist_lateral_2_m": 4.0,
        },
    ],
    "D1": [
        {
            "barcode": "7891000100002",
            "name": "Fio Dental",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100011",
            "name": "Sabão em Pó",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100015",
            "name": "Amaciante",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100051",
            "name": "Acém",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100069",
            "name": "Refrigerante Cola ",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "D2": [
        {
            "barcode": "7891000100004",
            "name": "Batata",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100006",
            "name": "Shampoo",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100021",
            "name": "Manteiga",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100031",
            "name": "Pão Francês",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100049",
            "name": "Sabão em Pó",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "E1": [
        {
            "barcode": "7891000100007",
            "name": "Leite Integral",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100016",
            "name": "Batata",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
        {
            "barcode": "7891000100034",
            "name": "Shampoo",
            "dist_lateral_1_m": 9.0,
            "dist_lateral_2_m": 11.0,
        },
        {
            "barcode": "7891000100041",
            "name": "Vinho Tinto",
            "dist_lateral_1_m": 13.0,
            "dist_lateral_2_m": 7.0,
        },
        {
            "barcode": "7891000100068",
            "name": "Biscoito Recheado",
            "dist_lateral_1_m": 17.0,
            "dist_lateral_2_m": 3.0,
        },
    ],
    "E2": [
        {
            "barcode": "7891000100000",
            "name": "Açúcar",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
        {
            "barcode": "7891000100001",
            "name": "Frango Inteiro ",
            "dist_lateral_1_m": 7.0,
            "dist_lateral_2_m": 13.0,
        },
        {
            "barcode": "7891000100018",
            "name": "Linguiça",
            "dist_lateral_1_m": 11.0,
            "dist_lateral_2_m": 9.0,
        },
        {
            "barcode": "7891000100027",
            "name": "Torrada",
            "dist_lateral_1_m": 15.0,
            "dist_lateral_2_m": 5.0,
        },
        {
            "barcode": "7891000100078",
            "name": "Biscoito",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "F1": [
        {
            "barcode": "7891000100020",
            "name": "Pão de Forma",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100035",
            "name": "Desinfetante",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100057",
            "name": "Frango Inteiro ",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100064",
            "name": "Pão Francês",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100067",
            "name": "Fio Dental",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
    "F2": [
        {
            "barcode": "7891000100010",
            "name": "Picanha",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100023",
            "name": "Presunto",
            "dist_lateral_1_m": 6.0,
            "dist_lateral_2_m": 14.0,
        },
        {
            "barcode": "7891000100033",
            "name": "Óleo de Soja",
            "dist_lateral_1_m": 10.0,
            "dist_lateral_2_m": 10.0,
        },
        {
            "barcode": "7891000100050",
            "name": "Feijão",
            "dist_lateral_1_m": 14.0,
            "dist_lateral_2_m": 6.0,
        },
        {
            "barcode": "7891000100079",
            "name": "Queijo Mussarela",
            "dist_lateral_1_m": 18.0,
            "dist_lateral_2_m": 2.0,
        },
    ],
}
