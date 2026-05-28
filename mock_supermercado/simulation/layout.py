"""Layout virtual editavel do supermercado.

Cada chave representa um corredor/estante. Dentro do corredor, cada produto
declara a distancia ate os dois corredores laterais que conectam as estantes.
"""

AISLE_GAP_METERS = 1.0
AISLE_LENGTH_METERS = 20.0


def _evenly_spaced_products(products):
    spacing_m = AISLE_LENGTH_METERS / (len(products) + 1)
    return [
        {**product, "dist_to_aisle_m": spacing_m * (index + 1)}
        for index, product in enumerate(products)
    ]


SUPERMARKET_LAYOUT = {
    "A1": _evenly_spaced_products([
        {"barcode": "7891000100008", "name": "Presunto"},
        {"barcode": "7891000100022", "name": "Manteiga sem sal"},
        {"barcode": "7891000100043", "name": "Biscoito Recheado"},
        {"barcode": "7891000100053", "name": "Suco de Laranja"},
        {"barcode": "7891000100075", "name": "Azeite"},
        {"barcode": "7891000100119", "name": "Leite"},
        {"barcode": "7891000100140", "name": "Picanha Especial"},
    ]),
    "A2": _evenly_spaced_products([
        {"barcode": "7891000100005", "name": "Milho"},
        {"barcode": "7891000100014", "name": "Pão Francês"},
        {"barcode": "7891000100019", "name": "Desodorante Dove Men"},
        {"barcode": "7891000100055", "name": "Queijo Mussarela"},
        {"barcode": "7891000100058", "name": "Torrada"},
        {"barcode": "7891000100086", "name": "Cebola"},
        {"barcode": "7891000100145", "name": "Desinfetante Natural"},
    ]),
    "B1": _evenly_spaced_products([
        {"barcode": "7891000100017", "name": "Óleo de girasol"},
        {"barcode": "7891000100037", "name": "Farinha"},
        {"barcode": "7891000100039", "name": "Macarrão"},
        {"barcode": "7891000100146", "name": "Iogurte Natural Natural"},
    ]),
    "B2": _evenly_spaced_products([
        {"barcode": "7891000100009", "name": "Torrada Tradicional"},
        {"barcode": "7891000100012", "name": "Tomate"},
        {"barcode": "7891000100013", "name": "Detergente"},
        {"barcode": "7891000100030", "name": "Cenoura Organica"},
        {"barcode": "7891000100056", "name": "Papel Higiênico"},
        {"barcode": "7891000100062", "name": "Água Sanitária Natural"},
        {"barcode": "7891000100072", "name": "Creme Dental"},
        {"barcode": "7891000100099", "name": "Farinha Natural"},
        {"barcode": "7891000100109", "name": "Água Sanitária"},
    ]),
    "C1": _evenly_spaced_products([
        {"barcode": "7891000100003", "name": "Cerveja Artesanal"},
        {"barcode": "7891000100025", "name": "Esponja de Aço"},
        {"barcode": "7891000100047", "name": "Creme de Leite"},
        {"barcode": "7891000100082", "name": "Café"},
        {"barcode": "7891000100084", "name": "Chá Gelado"},
    ]),
    "C2": _evenly_spaced_products([
        {"barcode": "7891000100026", "name": "Água Mineral"},
        {"barcode": "7891000100028", "name": "Leite Condensado"},
        {"barcode": "7891000100029", "name": "Salsicha"},
        {"barcode": "7891000100048", "name": "Sabonete "},
        {"barcode": "7891000100102", "name": "Maçã"},
        {"barcode": "7891000100116", "name": "Arroz"},
        {"barcode": "7891000100127", "name": "Biscoito Recheado Natural"},
    ]),
    "D1": _evenly_spaced_products([
        {"barcode": "7891000100002", "name": "Fio Dental"},
        {"barcode": "7891000100011", "name": "Sabão em Pó"},
        {"barcode": "7891000100015", "name": "Amaciante"},
        {"barcode": "7891000100051", "name": "Acém"},
        {"barcode": "7891000100065", "name": "Cerveja"},
        {"barcode": "7891000100069", "name": "Refrigerante Cola "},
        {"barcode": "7891000100149", "name": "Sabão em Pó Especial"},
    ]),
    "D2": _evenly_spaced_products([
        {"barcode": "7891000100004", "name": "Batata"},
        {"barcode": "7891000100006", "name": "Shampoo"},
        {"barcode": "7891000100021", "name": "Manteiga salgada"},
        {"barcode": "7891000100024", "name": "Desodorante"},
        {"barcode": "7891000100139", "name": "Açúcar Especial"},
    ]),
    "E1": _evenly_spaced_products([
        {"barcode": "7891000100007", "name": "Leite Integral"},
        {"barcode": "7891000100016", "name": "Batata Organica"},
        {"barcode": "7891000100038", "name": "Batata frita congelada"},
        {"barcode": "7891000100041", "name": "Vinho Tinto"},
        {"barcode": "7891000100044", "name": "Manteiga "},
        {"barcode": "7891000100073", "name": "Shampoo Natural"},
        {"barcode": "7891000100074", "name": "Torrada Natural"},
        {"barcode": "7891000100093", "name": "Alface"},
        {"barcode": "7891000100104", "name": "Bolo de Cenoura "},
        {"barcode": "7891000100134", "name": "Iogurte Natural"},
    ]),
    "E2": _evenly_spaced_products([
        {"barcode": "7891000100000", "name": "Açúcar"},
        {"barcode": "7891000100001", "name": "Frango Inteiro"},
        {"barcode": "7891000100018", "name": "Linguiça"},
        {"barcode": "7891000100027", "name": "Torrada integral"},
        {"barcode": "7891000100091", "name": "Requeijão"},
        {"barcode": "7891000100135", "name": "Batata Natural"},
    ]),
    "F1": _evenly_spaced_products([
        {"barcode": "7891000100020", "name": "Pão de Forma"},
        {"barcode": "7891000100035", "name": "Desinfetante"},
        {"barcode": "7891000100067", "name": "Fio Dental Natural"},
    ]),
    "F2": _evenly_spaced_products([
        {"barcode": "7891000100010", "name": "Picanha"},
        {"barcode": "7891000100033", "name": "Óleo"},
        {"barcode": "7891000100050", "name": "Feijão"},
    ]),
}
