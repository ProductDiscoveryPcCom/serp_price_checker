"""Análisis de precios y generación de recomendaciones."""

import logging
from typing import List, Optional
from statistics import median
from .models import (
    Product, ProductCluster, PriceAnalysis, 
    Recommendation, AnalysisConfig
)
from .token_matcher import (
    calculate_token_match, cluster_by_brand, MatchLevel
)

logger = logging.getLogger(__name__)


def identify_your_product(
    products: List[Product],
    your_domain: str,
    your_price: Optional[float] = None,
    your_url: Optional[str] = None
) -> Optional[Product]:
    """
    Identifica cuál de los productos es el tuyo.
    
    Prioridad:
    1. URL exacta (si se proporciona)
    2. Dominio + precio más cercano
    """
    # Primero: buscar por URL exacta
    if your_url:
        your_url_clean = your_url.lower().strip()
        for p in products:
            if p.url and p.url.lower().strip() == your_url_clean:
                return p
        # Buscar coincidencia parcial de URL
        for p in products:
            if p.url and (your_url_clean in p.url.lower() or p.url.lower() in your_url_clean):
                return p
    
    # Segundo: buscar por dominio
    your_domain_clean = your_domain.lower().replace('www.', '').strip()
    
    candidates = []
    for p in products:
        store_lower = (p.store or '').lower()
        url_lower = (p.url or '').lower()
        
        if your_domain_clean in store_lower or your_domain_clean in url_lower:
            candidates.append(p)
    
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    # Múltiples productos: elegir el más cercano a tu precio
    if your_price and your_price > 0:
        candidates.sort(key=lambda p: abs(p.price - your_price) if p.price else float('inf'))
    
    return candidates[0]


def cluster_products_by_brand(products: List[Product]) -> List[ProductCluster]:
    """Agrupa productos por marca detectada."""
    brand_groups = cluster_by_brand(products)
    
    clusters = []
    for brand, prods in brand_groups.items():
        if not prods:
            continue
        
        cluster = ProductCluster(
            key=brand,
            name=brand.title() if brand != 'otras' else 'Otras marcas',
            products=prods
        )
        clusters.append(cluster)
    
    # Ordenar por número de productos
    clusters.sort(key=lambda c: len(c.products), reverse=True)
    
    return clusters


def analyze_prices(
    products: List[Product],
    config: AnalysisConfig
) -> PriceAnalysis:
    """
    Realiza análisis completo de precios.
    """
    analysis = PriceAnalysis(
        query=config.product_query,
        your_domain=config.your_domain,
        your_price=config.your_price,
    )
    
    analysis.all_products = products
    analysis.total_products = len(products)
    
    # Productos con precio
    with_price = [p for p in products if p.has_price]
    analysis.total_with_price = len(with_price)
    
    if not with_price:
        logger.warning("No hay productos con precio para analizar")
        return analysis
    
    # Tiendas únicas
    stores = set(p.store for p in with_price if p.store)
    analysis.total_stores = len(stores)
    
    # === IDENTIFICAR TU PRODUCTO ===
    your_product = identify_your_product(
        products, 
        config.your_domain, 
        config.your_price,
        config.your_product_url
    )
    analysis.your_product = your_product
    
    # Todos los productos de tu tienda
    your_domain_clean = config.your_domain.lower().replace('www.', '')
    analysis.your_store_products = [
        p for p in products 
        if your_domain_clean in (p.store or '').lower() 
        or your_domain_clean in (p.url or '').lower()
    ]
    
    # === ESTADÍSTICAS DE PRECIO ===
    prices = sorted([p.price for p in with_price])
    analysis.min_price = prices[0]
    analysis.max_price = prices[-1]
    analysis.avg_price = sum(prices) / len(prices)
    analysis.median_price = median(prices)
    
    # Más barato
    analysis.cheapest = min(with_price, key=lambda x: x.price)
    
    # === POSICIÓN EN SERP ===
    for i, p in enumerate(products, 1):
        if p.is_your_product or (your_product and p.url == your_product.url):
            analysis.your_serp_position = i
            break
    
    # === RANKING DE PRECIO ===
    your_price = config.your_price
    analysis.products_cheaper = len([p for p in with_price if p.price < your_price])
    analysis.products_same = len([p for p in with_price if p.price == your_price])
    analysis.products_expensive = len([p for p in with_price if p.price > your_price])
    
    analysis.your_price_rank = analysis.products_cheaper + 1
    
    # === CALCULAR DIFERENCIAS DE PRECIO ===
    for product in products:
        if product.has_price and your_price > 0:
            product.price_diff_abs = product.price - your_price
            product.price_diff_pct = ((product.price - your_price) / your_price) * 100
    
    # === MATCHING CON TOKEN MATCHER ===
    reference_title = config.product_query
    if your_product:
        reference_title = your_product.title
    
    for p in with_price:
        if your_product and p.url == your_product.url:
            p.match_score = 1.0
            p.match_level = MatchLevel.EXACT
            continue
        
        match = calculate_token_match(p.title, reference_title)
        p.match_score = match.score
        p.match_level = match.level
        
        # Productos muy similares
        if match.level in [MatchLevel.EXACT, MatchLevel.VERY_SIMILAR]:
            analysis.exact_matches.append(p)
    
    # === CLUSTERING POR MARCA ===
    analysis.clusters = cluster_products_by_brand(with_price)
    
    # Encontrar tu cluster
    if your_product:
        for cluster in analysis.clusters:
            if your_product in cluster.products:
                analysis.your_cluster = cluster
                # Ranking dentro del cluster
                cluster_sorted = sorted(cluster.products, key=lambda x: x.price)
                for i, p in enumerate(cluster_sorted, 1):
                    if p.url == your_product.url or p.is_your_product:
                        analysis.your_price_rank_in_cluster = i
                        break
                break
    
    # === GENERAR RECOMENDACIONES ===
    analysis.recommendations = generate_recommendations(analysis, config)
    
    return analysis


def generate_recommendations(
    analysis: PriceAnalysis,
    config: AnalysisConfig
) -> List[Recommendation]:
    """Genera recomendaciones accionables basadas en el análisis."""
    recommendations = []
    
    your_price = config.your_price
    
    # === RECOMENDACIÓN DE PRECIO ===
    if analysis.cheapest and analysis.cheapest.price < your_price:
        gap = your_price - analysis.cheapest.price
        
        if analysis.your_price_rank > 3:
            # Para entrar en top 3
            prices_sorted = sorted([p.price for p in analysis.all_products if p.has_price])
            third_price = prices_sorted[2] if len(prices_sorted) >= 3 else analysis.cheapest.price
            gap_to_top3 = your_price - third_price
            
            if gap_to_top3 > 0:
                recommendations.append(Recommendation(
                    type="price_reduction",
                    priority="high",
                    title="Reducir precio para competir",
                    description=f"Estás en posición #{analysis.your_price_rank}. {analysis.cheapest.store} tiene el mejor precio.",
                    action=f"Baja {gap_to_top3:.2f}€ para entrar en el top 3",
                    impact=f"Pasarías de #{analysis.your_price_rank} a #3",
                    data={
                        "current_rank": analysis.your_price_rank,
                        "target_rank": 3,
                        "reduction_needed": gap_to_top3,
                        "competitor": analysis.cheapest.store
                    }
                ))
        elif analysis.your_price_rank > 1:
            recommendations.append(Recommendation(
                type="price_reduction",
                priority="medium",
                title="Oportunidad de liderazgo",
                description=f"Estás a {gap:.2f}€ de tener el mejor precio.",
                action=f"Baja {gap:.2f}€ para ser el más barato",
                impact=f"Pasarías de #{analysis.your_price_rank} a #1",
                data={
                    "current_rank": analysis.your_price_rank,
                    "reduction_needed": gap,
                    "competitor": analysis.cheapest.store
                }
            ))
    
    # === YA ERES EL MÁS BARATO ===
    if analysis.your_price_rank == 1 and analysis.total_with_price > 1:
        prices_sorted = sorted([p for p in analysis.all_products if p.has_price], key=lambda x: x.price)
        if len(prices_sorted) > 1:
            second_cheapest = prices_sorted[1]
            margin = second_cheapest.price - your_price
            
            if margin > 20:
                recommendations.append(Recommendation(
                    type="price_increase",
                    priority="medium",
                    title="Margen de subida",
                    description=f"Eres el más barato con {margin:.2f}€ de ventaja sobre {second_cheapest.store}.",
                    action=f"Podrías subir hasta {margin * 0.7:.2f}€ y seguir siendo competitivo",
                    impact="Aumentar margen manteniendo posición",
                    data={
                        "margin_available": margin,
                        "recommended_increase": margin * 0.7,
                        "next_competitor": second_cheapest.store,
                        "next_price": second_cheapest.price
                    }
                ))
    
    # === PRODUCTOS MUY SIMILARES MÁS BARATOS ===
    similar_cheaper = [
        p for p in analysis.exact_matches 
        if p.price < your_price
    ]
    if similar_cheaper:
        cheapest_similar = min(similar_cheaper, key=lambda x: x.price)
        gap = your_price - cheapest_similar.price
        
        recommendations.append(Recommendation(
            type="similar_product_alert",
            priority="high",
            title=f"🎯 Producto muy similar más barato",
            description=f"{cheapest_similar.store} tiene un producto equivalente a {cheapest_similar.price:.2f}€ ({gap:.2f}€ menos que tú).",
            action=f"Revisa si es el mismo producto y ajusta precio",
            impact="Pérdida directa de ventas",
            data={
                "competitor": cheapest_similar.store,
                "competitor_price": cheapest_similar.price,
                "gap": gap,
                "product": cheapest_similar.title[:60]
            }
        ))
    
    # === OFERTAS DE COMPETIDORES ===
    offers = [p for p in analysis.all_products if p.is_offer and p.has_price]
    aggressive_offers = [p for p in offers if p.discount_pct and p.discount_pct > 15]
    
    if aggressive_offers:
        stores = list(set(p.store for p in aggressive_offers[:3]))
        recommendations.append(Recommendation(
            type="alert",
            priority="high",
            title=f"⚠️ {len(aggressive_offers)} competidores con ofertas agresivas",
            description=f"Hay descuentos de más del 15% en tiendas como {', '.join(stores)}.",
            action="Monitoriza estas ofertas y considera responder",
            impact="Riesgo de perder ventas por ofertas temporales",
            data={
                "offers": [{"store": p.store, "discount": p.discount_pct, "price": p.price} for p in aggressive_offers[:5]]
            }
        ))
    
    # === MÚLTIPLES PRODUCTOS TU TIENDA ===
    if len(analysis.your_store_products) > 1:
        recommendations.append(Recommendation(
            type="opportunity",
            priority="low",
            title=f"📦 {len(analysis.your_store_products)} productos tuyos aparecen",
            description="Tienes múltiples productos posicionados para esta búsqueda.",
            action="Revisa si todos son relevantes o hay canibalización",
            impact="Optimizar catálogo visible",
            data={
                "products": [{"title": p.title[:50], "price": p.price} for p in analysis.your_store_products]
            }
        ))
    
    # === NO APARECES ===
    if not analysis.your_serp_position and not analysis.your_store_products:
        recommendations.append(Recommendation(
            type="alert",
            priority="high",
            title="❌ No apareces en los resultados",
            description="Tu tienda no está visible para esta búsqueda.",
            action="Revisa tu feed de productos y campañas de Shopping",
            impact="Pérdida total de visibilidad",
            data={}
        ))
    
    # Ordenar por prioridad
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))
    
    return recommendations
