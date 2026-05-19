"""
Smart Cart 360 -- Classificador Naive Bayes para Recomendacao (Etapa C)
========================================================================

Implementacao de um classificador Naive Bayes adaptado para o problema
de recomendacao de produtos em supermercado. Este modulo existe como
ALTERNATIVA ao algoritmo principal (recommendations.py) para fins de
COMPARACAO no TCC. Nao substitui o algoritmo principal.

Fundamentacao teorica:
    O Naive Bayes e um classificador probabilistico baseado no Teorema
    de Bayes com a suposicao "naive" de independencia condicional entre
    as features (produtos no carrinho).

    Teorema de Bayes:
        P(B | A) = P(A | B) * P(B) / P(A)

    Aplicado ao nosso problema:
        P(candidato | carrinho) = P(carrinho | candidato) * P(candidato) / P(carrinho)

    Onde:
        - P(candidato | carrinho) = probabilidade posterior de o cliente
          querer o produto candidato, dado o que ja tem no carrinho.
          E isso que queremos calcular (posterior probability).

        - P(carrinho | candidato) = likelihood. Probabilidade de observar
          os itens do carrinho em compras que continham o candidato.
          Com a suposicao naive de independencia:
              P(carrinho | candidato) = PRODUTO de P(item_i | candidato)
              para cada item_i no carrinho.

        - P(candidato) = prior probability. Frequencia geral do produto
          candidato no historico de compras.

        - P(carrinho) = evidence. Constante para todos os candidatos,
          pode ser ignorada no ranking (nao afeta a ordenacao).

    A suposicao "naive" de independencia:
        Assumimos que a presenca de cada produto no carrinho e independente
        da presenca dos outros, dado o candidato. Na pratica isso nao e
        verdade (quem compra arroz provavelmente compra feijao), mas o
        Naive Bayes funciona surpreendentemente bem mesmo com essa
        simplificacao (Negre, 2015; Domingos & Pazzani, 1997).

    Laplace Smoothing (alpha):
        Para evitar probabilidades zero (quando um produto do carrinho
        nunca apareceu junto com o candidato), aplicamos suavizacao de
        Laplace:
            P_suavizado(item | candidato) = (count + alpha) / (total + alpha * V)
        Onde V e o tamanho do vocabulario (total de produtos distintos).
        Isso garante que nenhuma probabilidade seja zero, evitando que
        um unico produto "mate" toda a probabilidade no produto.

    Uso de log-probabilidades:
        Como o produto de muitas probabilidades pequenas pode causar
        underflow numerico, usamos log-probabilidades:
            log P(candidato | carrinho) = log P(candidato)
                + SUM de log P(item_i | candidato)
        A soma de logs e equivalente ao produto das probabilidades.

    Integracao com o grafo de localizacao:
        O score final combina a probabilidade do Naive Bayes com o
        score do grafo de localizacao do Joao (quando disponivel),
        criando um sistema hibrido analogo ao do algoritmo principal.

Referencias:
    - Bayes, T. (1763). An Essay towards solving a Problem in the
      Doctrine of Chances. Philosophical Transactions of the Royal
      Society of London, 53, 370-418.
    - Negre, E. (2015). Information and Recommender Systems.
      Cap. 3.5.2: Association Rules; Cap. 4: Hybrid Systems.
    - Domingos, P. & Pazzani, M. (1997). On the Optimality of the
      Simple Bayesian Classifier under Zero-One Loss. Machine
      Learning, 29, 103-130.
    - Linden, G., Smith, B. & York, J. (2003). Amazon.com
      Recommendations: Item-to-Item Collaborative Filtering.
      IEEE Internet Computing, 7(1), 76-80.
    - Zhang, H. (2004). The Optimality of Naive Bayes.
      Proc. FLAIRS Conference.
    - Oracle. Recommendation Algorithms: Transactional Naive Bayes.
      Oracle Data Mining Concepts, 21c.

Autores: [Seu nome aqui]
Projeto: Smart Cart 360 -- TCC Insper 2026
"""

import math
import sqlite3
from collections import defaultdict

from servidor_central.algorithms.location_graph import (
    get_connected_links,
    load_location_graph,
)
from servidor_central.database import get_connection
from servidor_central.schemas import (
    CartResponse,
    PromotionResponse,
    RecommendationResponse,
)

# Numero maximo de recomendacoes
MAX_RECOMMENDATIONS = 20

# Laplace smoothing parameter (alpha)
# alpha = 1.0 e o padrao (Laplace smoothing classico)
# alpha < 1.0 e Lidstone smoothing (menos suavizacao)
LAPLACE_ALPHA = 1.0


# ---------------------------------------------------------------------------
# 1. CONSTRUCAO DO MODELO NAIVE BAYES
# ---------------------------------------------------------------------------
# O modelo e construido a partir do historico de compras. Para cada
# produto candidato B, calculamos:
#
#   P(B) = prior = numero de compras com B / total de compras
#   P(item_i | B) = likelihood = compras com item_i E B / compras com B
#
# Com Laplace smoothing:
#   P(item_i | B) = (compras com item_i E B + alpha) / (compras com B + alpha * V)
#
# Onde V = total de produtos distintos no historico.
# ---------------------------------------------------------------------------

class NaiveBayesModel:
    """
    Modelo Naive Bayes treinado a partir do historico de compras.

    O modelo armazena:
        - priors: P(candidato) para cada produto
        - likelihoods: P(item | candidato) para cada par
        - n_transactions: total de transacoes no historico
        - n_products: total de produtos distintos (vocabulario V)

    O modelo e construido uma vez e reutilizado para multiplas
    recomendacoes (eficiente para uso em producao).
    """

    def __init__(self):
        self.priors = {}              # barcode -> P(barcode)
        self.likelihoods = {}         # (item, candidate) -> P(item | candidate)
        self.candidate_counts = {}    # barcode -> num compras com esse produto
        self.n_transactions = 0       # total de compras
        self.n_products = 0           # vocabulario V
        self.is_trained = False

    def train(self, conn):
        """
        Treina o modelo a partir do historico de compras no banco de dados.

        Passo 1: Contar total de transacoes e produtos distintos.
        Passo 2: Para cada produto, contar em quantas transacoes apareceu (prior).
        Passo 3: Para cada par (item, candidato), contar co-ocorrencias (likelihood).

        Args:
            conn: conexao SQLite com purchase_history e purchase_items.
        """
        # --- Passo 1: Totais ---
        self.n_transactions = conn.execute(
            "SELECT COUNT(DISTINCT purchase_id) FROM purchase_items"
        ).fetchone()[0]

        if self.n_transactions == 0:
            self.is_trained = False
            return

        self.n_products = conn.execute(
            "SELECT COUNT(DISTINCT barcode) FROM purchase_items"
        ).fetchone()[0]

        # --- Passo 2: Priors P(candidato) ---
        # P(candidato) = compras_com_candidato / total_compras
        rows = conn.execute(
            "SELECT barcode, COUNT(DISTINCT purchase_id) as cnt "
            "FROM purchase_items "
            "GROUP BY barcode"
        ).fetchall()

        for barcode, cnt in rows:
            self.priors[barcode] = cnt / self.n_transactions
            self.candidate_counts[barcode] = cnt

        # --- Passo 3: Co-ocorrencias para likelihoods ---
        # Para cada par (item_i, candidato_B), contamos quantas
        # transacoes contem AMBOS. Isso e o numerador do likelihood.
        #
        # Usamos uma query que faz o join da tabela consigo mesma:
        # para cada transacao, cada par de produtos distintos gera
        # uma co-ocorrencia.
        rows = conn.execute(
            "SELECT pi1.barcode as item, pi2.barcode as candidate, "
            "       COUNT(DISTINCT pi1.purchase_id) as co_count "
            "FROM purchase_items pi1 "
            "JOIN purchase_items pi2 ON pi1.purchase_id = pi2.purchase_id "
            "WHERE pi1.barcode != pi2.barcode "
            "GROUP BY pi1.barcode, pi2.barcode"
        ).fetchall()

        for item, candidate, co_count in rows:
            self.likelihoods[(item, candidate)] = co_count

        self.is_trained = True

    def get_likelihood(self, item_barcode, candidate_barcode):
        """
        Calcula P(item | candidato) com Laplace smoothing.

        P(item | candidato) = (co_ocorrencias + alpha) / (compras_candidato + alpha * V)

        Onde:
            - co_ocorrencias = transacoes com item E candidato
            - compras_candidato = transacoes com candidato
            - alpha = parametro de suavizacao (default 1.0)
            - V = total de produtos distintos (vocabulario)

        O Laplace smoothing garante que P nunca e zero, evitando
        que um unico item desconhecido "mate" toda a probabilidade.
        """
        co_count = self.likelihoods.get((item_barcode, candidate_barcode), 0)
        candidate_total = self.candidate_counts.get(candidate_barcode, 0)

        numerator = co_count + LAPLACE_ALPHA
        denominator = candidate_total + LAPLACE_ALPHA * self.n_products

        if denominator == 0:
            return LAPLACE_ALPHA / (LAPLACE_ALPHA * max(self.n_products, 1))

        return numerator / denominator

    def predict_score(self, cart_barcodes, candidate_barcode):
        """
        Calcula o log-posterior P(candidato | carrinho) para um candidato.

        Usando Bayes com suposicao naive de independencia:
            log P(candidato | carrinho) = log P(candidato)
                + SUM_i log P(item_i | candidato)

        O termo P(carrinho) e ignorado porque e constante para todos
        os candidatos (nao afeta o ranking).

        Usamos log-probabilidades para evitar underflow numerico
        (produto de muitas probabilidades pequenas -> 0).

        Args:
            cart_barcodes: set com TODOS os barcodes no carrinho.
            candidate_barcode: barcode do produto candidato.

        Returns:
            Log-posterior score (float). Maior = mais provavel.
        """
        if not self.is_trained:
            return float("-inf")

        if candidate_barcode not in self.priors:
            return float("-inf")

        # Log-prior: log P(candidato)
        log_score = math.log(self.priors[candidate_barcode])

        # Log-likelihoods: SUM de log P(item_i | candidato)
        # Aqui usamos TODOS os itens do carrinho (cesta completa).
        for item_bc in cart_barcodes:
            if item_bc == candidate_barcode:
                continue
            likelihood = self.get_likelihood(item_bc, candidate_barcode)
            log_score += math.log(likelihood)

        return log_score


# ---------------------------------------------------------------------------
# 2. GRAFO DE LOCALIZACAO (reutilizado do algoritmo principal)
# ---------------------------------------------------------------------------

def _get_graph_scores(last_barcode, graph):
    """
    Reutiliza a logica do grafo de localizacao do Joao.
    Identica a implementacao em recommendations.py.
    """
    product_scores = {}
    aisle_scores = {}

    if not graph or not last_barcode:
        return product_scores, aisle_scores

    links = get_connected_links(graph, last_barcode)
    if not links:
        return product_scores, aisle_scores

    nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
    total = len(links)

    for index, link in enumerate(links):
        neighbor_barcode = (
            link["target"] if link.get("source") == last_barcode else link.get("source")
        )
        score = 1.0 - (index / max(total, 1))
        product_scores.setdefault(neighbor_barcode, score)

        aisle = nodes_by_id.get(neighbor_barcode, {}).get("aisle")
        if aisle:
            aisle_scores.setdefault(aisle, score)

    return product_scores, aisle_scores


# ---------------------------------------------------------------------------
# 3. SCORING COMBINADO (Naive Bayes + Grafo)
# ---------------------------------------------------------------------------
# O score final combina a probabilidade posterior do Naive Bayes com
# fatores do grafo de localizacao e desconto, criando um sistema
# hibrido (Negre, 2015, Cap. 4).
#
# Pesos:
#   - Naive Bayes posterior (0-40 pts): fator probabilistico principal
#   - Grafo de localizacao (0-30 pts): proximidade espacial
#   - Desconto (0-20 pts): incentivo economico
#   - Corredor (0-10 pts): conveniencia
# ---------------------------------------------------------------------------

def _score_promotion_nb(
    promo,
    nb_scores,
    graph_product_scores,
    graph_aisle_scores,
    cart_aisles,
    cart_total,
):
    """
    Calcula score hibrido combinando Naive Bayes + grafo + desconto.

    Args:
        promo: promocao candidata.
        nb_scores: dict barcode -> score normalizado [0, 1] do Naive Bayes.
        graph_product_scores: scores do grafo por produto.
        graph_aisle_scores: scores do grafo por corredor.
        cart_aisles: corredores dos itens no carrinho.
        cart_total: valor total do carrinho.

    Returns:
        Score numerico (float). Maior = mais relevante.
    """
    score = 0.0
    barcode = promo.product_barcode or ""

    # --- Fator 1: Naive Bayes posterior (0-40 pts) ---
    # Score normalizado [0, 1] derivado do log-posterior.
    # O candidato com maior probabilidade posterior recebe 40 pts.
    if barcode in nb_scores:
        score += 40.0 * nb_scores[barcode]

    # --- Fator 2: Proximidade no grafo de localizacao (0-30 pts) ---
    if barcode in graph_product_scores:
        score += 30.0 * graph_product_scores[barcode]
    elif promo.aisle and promo.aisle in graph_aisle_scores:
        score += 20.0 * graph_aisle_scores[promo.aisle]

    # --- Fator 3: Atratividade do desconto (0-20 pts) ---
    if promo.discount_value and promo.discount_value > 0:
        if promo.discount_type == "percentage":
            score += 20.0 * min(promo.discount_value / 100.0, 1.0)
        elif promo.discount_type == "fixed":
            if cart_total > 0:
                ratio = promo.discount_value / cart_total
                score += 20.0 * min(ratio * 5, 1.0)
            else:
                score += 10.0

    # --- Fator 4: Proximidade de corredor (0-10 pts) ---
    if promo.aisle and promo.aisle in cart_aisles:
        score += 10.0
    elif promo.aisle and cart_aisles:
        promo_zone = promo.aisle[0] if promo.aisle else ""
        for aisle in cart_aisles:
            if aisle and aisle[0] == promo_zone:
                score += 5.0
                break

    return round(score, 2)


# ---------------------------------------------------------------------------
# 4. FUNCAO PRINCIPAL -- generate_recommendations_naive_bayes
# ---------------------------------------------------------------------------

# Cache global do modelo (treinado uma vez, reutilizado)
_nb_model_cache = None


def get_trained_model(force_retrain=False):
    """
    Retorna o modelo Naive Bayes treinado (com cache).

    O modelo e treinado uma vez a partir do historico e reutilizado
    em chamadas subsequentes. Use force_retrain=True para retreinar
    (ex: apos adicionar novos dados ao historico).
    """
    global _nb_model_cache

    if _nb_model_cache is not None and not force_retrain:
        return _nb_model_cache

    model = NaiveBayesModel()
    try:
        conn = get_connection()
        try:
            model.train(conn)
        finally:
            conn.close()
    except Exception:
        pass

    _nb_model_cache = model
    return model


def generate_recommendations_naive_bayes(
    cart,
    all_promotions=None,
    *,
    last_barcode=None,
    graph=None,
    model=None,
):
    """
    Gera recomendacoes usando Naive Bayes + grafo de localizacao.

    Este e um algoritmo ALTERNATIVO ao principal (recommendations.py)
    para fins de comparacao no TCC. Nao substitui o algoritmo principal.

    Fluxo:
        1. Carregar/treinar modelo Naive Bayes (com cache)
        2. Carregar grafo de localizacao
        3. Extrair contexto da CESTA COMPLETA
        4. Calcular log-posterior P(candidato | carrinho) para cada candidato
        5. Normalizar scores para [0, 1]
        6. Combinar com grafo + desconto + corredor
        7. Ordenar e retornar top N

    A cesta COMPLETA e usada como evidencia: cada item no carrinho
    contribui com um fator de likelihood para o posterior de cada
    candidato (suposicao naive de independencia).

    Args:
        cart: Estado atual do carrinho (TODOS os itens).
        all_promotions: Lista de todas as promocoes.
        last_barcode: Ultimo produto escaneado (para o grafo).
        graph: Grafo de localizacao pre-carregado.
        model: Modelo NaiveBayesModel pre-treinado (opcional).

    Returns:
        RecommendationResponse com as promocoes recomendadas.
    """
    if not all_promotions:
        all_promotions = []

    # --- Carregar modelo ---
    if model is None:
        model = get_trained_model()

    # --- Carregar grafo ---
    if graph is None:
        graph = load_location_graph()

    if last_barcode is None and cart.items:
        last_barcode = cart.items[-1].barcode

    has_graph = graph is not None and bool(graph.get("links"))

    # --- Carrinho vazio -> retorna por maior desconto ---
    if not cart.items:
        sorted_promos = sorted(
            all_promotions,
            key=lambda p: p.discount_value or 0,
            reverse=True,
        )
        return RecommendationResponse(
            cart_id=cart.cart_id,
            algorithm_status="ready" if has_graph else "cache_missing",
            recommendations=sorted_promos[:MAX_RECOMMENDATIONS],
        )

    # --- Extrair contexto da cesta COMPLETA ---
    cart_barcodes = {item.barcode for item in cart.items}
    cart_aisles = {item.aisle for item in cart.items if item.aisle}

    # --- Filtrar promocoes ja no carrinho ---
    candidates = [
        promo for promo in all_promotions
        if promo.product_barcode not in cart_barcodes
    ]

    # --- Calcular log-posteriors do Naive Bayes ---
    # Para cada candidato, calculamos:
    #   log P(candidato | carrinho) = log P(candidato) + SUM log P(item_i | candidato)
    raw_scores = {}
    for promo in candidates:
        bc = promo.product_barcode
        if bc:
            raw_scores[bc] = model.predict_score(cart_barcodes, bc)

    # --- Normalizar para [0, 1] ---
    # Usamos min-max normalization nos log-posteriors.
    # Candidatos desconhecidos (score -inf) recebem 0.
    finite_scores = {bc: s for bc, s in raw_scores.items() if s != float("-inf")}
    nb_scores = {}

    if finite_scores:
        min_score = min(finite_scores.values())
        max_score = max(finite_scores.values())
        score_range = max_score - min_score

        if score_range > 0:
            nb_scores = {
                bc: (s - min_score) / score_range
                for bc, s in finite_scores.items()
            }
        else:
            # Todos os scores iguais -> todos recebem 1.0
            nb_scores = {bc: 1.0 for bc in finite_scores}

    # --- Scores do grafo ---
    graph_product_scores, graph_aisle_scores = _get_graph_scores(
        last_barcode, graph
    )

    # --- Calcular scores combinados ---
    scored = []
    for promo in candidates:
        s = _score_promotion_nb(
            promo=promo,
            nb_scores=nb_scores,
            graph_product_scores=graph_product_scores,
            graph_aisle_scores=graph_aisle_scores,
            cart_aisles=cart_aisles,
            cart_total=cart.total_amount,
        )
        scored.append((s, promo))

    # --- Ordenar e retornar ---
    scored.sort(key=lambda x: x[0], reverse=True)
    top_promos = [promo for _, promo in scored[:MAX_RECOMMENDATIONS]]

    # --- Status ---
    if not model.is_trained and not has_graph:
        status = "insufficient_data"
    elif not has_graph:
        status = "cache_missing"
    elif last_barcode and not graph_product_scores:
        status = "product_not_in_graph"
    else:
        status = "ready"

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status=status,
        recommendations=top_promos,
    )