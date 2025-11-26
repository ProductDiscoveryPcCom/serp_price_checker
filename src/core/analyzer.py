"""Análisis de precios y generación de recomendaciones."""

import logging
from typing import List, Optional
from statistics import median
from .models import (
    Product, ProductCluster, PriceAnalysis, 
    Recommendation, AnalysisConfig, MatchLevel
)
from .matcher import (
    cluster_products, identify_your_product, 
    calculate_match_score, extract_specs_from_title
)

logger = logging.getLogger(__name__)


def analyze_prices(
    products: List[Product],
    config: AnalysisConfig
) -> PriceAnalysis:
    """
    Realiza análisis completo de precios.
    
    Args:
        products: Lista de productos a analizar
        config: Configuración del análisis
        
    Returns:
        Análisis completo con estadísticas y recomendaciones
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
    your_product = identify_your_product(products, config.your_domain, config.your_price)
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
    sorted_by_price = sorted(with_price, key=lambda x: x.price)
    
    your_price = config.your_price
    analysis.products_cheaper = len([p for p in sorted_by_price if p.price < your_price])
    analysis.products_same = len([p for p in sorted_by_price if p.price == your_price])
    analysis.products_expensive = len([p for p in sorted_by_price if p.price > your_price])
    
    analysis.your_price_rank = analysis.products_cheaper + 1
    
    # === CALCULAR DIFERENCIAS DE PRECIO ===
    for product in products:
        if product.has_price and your_price > 0:
            product.price_diff_abs = product.price - your_price
            product.price_diff_pct = ((product.price - your_price) / your_price) * 100
    
    # === CLUSTERING ===
    analysis.clusters = cluster_products(with_price)
    
    # Encontrar cluster de tu producto
    if your_product and your_product.specs:
        your_key = your_product.specs.get_tier_key()
        for cluster in analysis.clusters:
            if cluster.key == your_key:
                analysis.your_cluster = cluster
                # Ranking dentro del cluster
                cluster_sorted = sorted(cluster.products, key=lambda x: x.price)
                for i, p in enumerate(cluster_sorted, 1):
                    if p.url == your_product.url or p.is_your_product:
                        analysis.your_price_rank_in_cluster = i
                        break
                break
    
    # === PRODUCTOS EXACTOS ===
    if your_product:
        for p in with_price:
            if p.url == your_product.url:
                continue
            score, level = calculate_match_score(p, your_product)
            p.match_score = score
            p.match_level = level
            if level in [MatchLevel.EXACT, MatchLevel.EQUIVALENT]:
                analysis.exact_matches.append(p)
    
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
        gap_pct = (gap / your_price) * 100
        
        if analysis.your_price_rank > 3:
            # Para entrar en top 3
            third_price = sorted([p.price for p in analysis.all_products if p.has_price])[2] if len([p for p in analysis.all_products if p.has_price]) >= 3 else analysis.cheapest.price
            gap_to_top3 = your_price - third_price
            
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
        second_cheapest = sorted([p for p in analysis.all_products if p.has_price], key=lambda x: x.price)[1]
        margin = second_cheapest.price - your_price
        
        if margin > 20:  # Si hay margen de más de 20€
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
    
    # === ANÁLISIS DE CLUSTER ===
    if analysis.your_cluster and len(analysis.your_cluster.products) > 1:
        cluster = analysis.your_cluster
        cluster_avg = cluster.avg_price
        
        if your_price > cluster_avg * 1.1:  # Más de 10% sobre la media del cluster
            diff = your_price - cluster_avg
            recommendations.append(Recommendation(
                type="cluster_analysis",
                priority="high",
                title="Precio alto vs competencia directa",
                description=f"Tu precio está {diff:.2f}€ por encima de la media de productos similares ({cluster.name}).",
                action=f"Considera ajustar a {cluster_avg:.2f}€ para igualar la media",
                impact="Mejorar competitividad en tu segmento",
                data={
                    "cluster_name": cluster.name,
                    "cluster_avg": cluster_avg,
                    "your_price": your_price,
                    "diff": diff
                }
            ))
    
    # === OFERTAS DE COMPETIDORES ===
    offers = [p for p in analysis.all_products if p.is_offer and p.has_price]
    aggressive_offers = [p for p in offers if p.discount_pct and p.discount_pct > 15]
    
    if aggressive_offers:
        recommendations.append(Recommendation(
            type="alert",
            priority="high",
            title=f"⚠️ {len(aggressive_offers)} competidores con ofertas agresivas",
            description=f"Hay descuentos de más del 15% en tiendas como {', '.join(set(p.store for p in aggressive_offers[:3]))}.",
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


def calculate_price_stats_for_cluster(
    cluster: ProductCluster,
    your_price: float
) -> dict:
    """Calcula estadísticas de precio para un cluster específico."""
    prices = [p.price for p in cluster.products if p.has_price]
    
    if not prices:
        return {}
    
    return {
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
        "median": median(prices),
        "count": len(prices),
        "your_rank": len([p for p in prices if p < your_price]) + 1,
        "cheaper_than_you": len([p for p in prices if p < your_price]),
        "same_as_you": len([p for p in prices if p == your_price]),
        "more_expensive": len([p for p in prices if p > your_price]),
    }
