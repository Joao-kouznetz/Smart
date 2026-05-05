"""Layout virtual editavel do supermercado.

Cada chave representa um corredor/estante. Dentro do corredor, cada produto
declara a distancia ate os dois corredores laterais que conectam as estantes.
"""

AISLE_GAP_METERS = 1.0

SUPERMARKET_LAYOUT = {
    "A1": [
        {
            "barcode": "7891000100008",
            "name": "Presunto",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100022",
            "name": "Manteiga sem sal",
            "dist_to_aisle_m": 5.0,
        },
        {
            "barcode": "7891000100043",
            "name": "Biscoito Recheado",
            "dist_to_aisle_m": 9.0,
        },
        {
            "barcode": "7891000100053",
            "name": "Suco de Laranja",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100075",
            "name": "Azeite",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "A2": [
        {
            "barcode": "7891000100005",
            "name": "Milho",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100014",
            "name": "Pão Francês",
            "dist_to_aisle_m": 5.0,
        },
        {
            "barcode": "7891000100054",
            "name": "Feijão",
            "dist_to_aisle_m": 9.0,
        },
        {
            "barcode": "7891000100055",
            "name": "Queijo Mussarela",
            "dist_to_aisle_m": 13.0,
        },
        {
            "barcode": "7891000100059",
            "name": "Vinho Tinto",
            "dist_to_aisle_m": 17.0,
        },
    ],
    "B1": [
        {
            "barcode": "7891000100017",
            "name": "Óleo de girasol",
            "dist_to_aisle_m": 3.0,
        },
        {
            "barcode": "7891000100037",
            "name": "Farinha",
            "dist_to_aisle_m": 7.0,
        },
        {
            "barcode": "7891000100039",
            "name": "Macarrão",
            "dist_to_aisle_m": 11.0,
        },
        {
            "barcode": "7891000100045",
            "name": "Esponja de Aço",
            "dist_to_aisle_m": 15.0,
        },
        {
            "barcode": "7891000100076",
            "name": "Acém",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "B2": [
        {
            "barcode": "7891000100009",
            "name": "Torrada Tradicional",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100012",
            "name": "Tomate",
            "dist_to_aisle_m": 6.0,
        },
        {
            "barcode": "7891000100013",
            "name": "Detergente",
            "dist_to_aisle_m": 10.0,
        },
        {
            "barcode": "7891000100030",
            "name": "Cenoura Organica",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100056",
            "name": "Papel Higiênico",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "C1": [
        {
            "barcode": "7891000100003",
            "name": "Cerveja Artesanal",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100025",
            "name": "Esponja de Aço",
            "dist_to_aisle_m": 6.0,
        },
        {
            "barcode": "7891000100046",
            "name": "Sabão em Pó ",
            "dist_to_aisle_m": 10.0,
        },
        {
            "barcode": "7891000100047",
            "name": "Creme de Leite",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100082",
            "name": "Café",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "C2": [
        {
            "barcode": "7891000100026",
            "name": "Água Mineral",
            "dist_to_aisle_m": 3.0,
        },
        {
            "barcode": "7891000100028",
            "name": "Leite Condensado",
            "dist_to_aisle_m": 8.0,
        },
        {
            "barcode": "7891000100029",
            "name": "Salsicha",
            "dist_to_aisle_m": 12.0,
        },
        {
            "barcode": "7891000100048",
            "name": "Sabonete ",
            "dist_to_aisle_m": 16.0,
        },
    ],
    "D1": [
        {
            "barcode": "7891000100002",
            "name": "Fio Dental",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100011",
            "name": "Sabão em Pó",
            "dist_to_aisle_m": 6.0,
        },
        {
            "barcode": "7891000100015",
            "name": "Amaciante",
            "dist_to_aisle_m": 10.0,
        },
        {
            "barcode": "7891000100051",
            "name": "Acém",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100069",
            "name": "Refrigerante Cola ",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "D2": [
        {
            "barcode": "7891000100004",
            "name": "Batata",
            "dist_to_aisle_m": 3.0,
        },
        {
            "barcode": "7891000100006",
            "name": "Shampoo",
            "dist_to_aisle_m": 7.0,
        },
        {
            "barcode": "7891000100021",
            "name": "Manteiga salgada",
            "dist_to_aisle_m": 11.0,
        },
        {
            "barcode": "7891000100031",
            "name": "Pão Francês",
            "dist_to_aisle_m": 15.0,
        },
        {
            "barcode": "7891000100049",
            "name": "Sabão em Pó",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "E1": [
        {
            "barcode": "7891000100007",
            "name": "Leite Integral",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100016",
            "name": "Batata Organica",
            "dist_to_aisle_m": 5.0,
        },
        {
            "barcode": "7891000100034",
            "name": "Shampoo",
            "dist_to_aisle_m": 9.0,
        },
        {
            "barcode": "7891000100041",
            "name": "Vinho Tinto",
            "dist_to_aisle_m": 13.0,
        },
        {
            "barcode": "7891000100068",
            "name": "Biscoito Recheado",
            "dist_to_aisle_m": 17.0,
        },
    ],
    "E2": [
        {
            "barcode": "7891000100000",
            "name": "Açúcar",
            "dist_to_aisle_m": 3.0,
        },
        {
            "barcode": "7891000100001",
            "name": "Frango Inteiro",
            "dist_to_aisle_m": 7.0,
        },
        {
            "barcode": "7891000100018",
            "name": "Linguiça",
            "dist_to_aisle_m": 11.0,
        },
        {
            "barcode": "7891000100027",
            "name": "Torrada integral",
            "dist_to_aisle_m": 15.0,
        },
        {
            "barcode": "7891000100078",
            "name": "Biscoito Recheado",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "F1": [
        {
            "barcode": "7891000100020",
            "name": "Pão de Forma",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100035",
            "name": "Desinfetante",
            "dist_to_aisle_m": 6.0,
        },
        {
            "barcode": "7891000100057",
            "name": "Frango Inteiro ",
            "dist_to_aisle_m": 10.0,
        },
        {
            "barcode": "7891000100064",
            "name": "Pão Francês",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100067",
            "name": "Fio Dental Natural",
            "dist_to_aisle_m": 18.0,
        },
    ],
    "F2": [
        {
            "barcode": "7891000100010",
            "name": "Picanha",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100023",
            "name": "Presunto",
            "dist_to_aisle_m": 6.0,
        },
        {
            "barcode": "7891000100033",
            "name": "Óleo",
            "dist_to_aisle_m": 10.0,
        },
        {
            "barcode": "7891000100050",
            "name": "Feijão",
            "dist_to_aisle_m": 14.0,
        },
        {
            "barcode": "7891000100079",
            "name": "Queijo Mussarela",
            "dist_to_aisle_m": 18.0,
        },
    ],
}
