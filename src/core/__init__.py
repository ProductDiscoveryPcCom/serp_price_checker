"""Core business logic."""

from .models import (
    Product,
    ProductSpecs,
    ProductCluster,
    PriceAnalysis,
    Recommendation,
    AnalysisConfig,
    MatchLevel,
    ResultType,
)

from .matcher import (
    extract_specs_from_title,
    calculate_match_score,
    calculate_text_similarity,
    cluster_products,
    find_matching_products,
    identify_your_product,
)

from .analyzer import (
    analyze_prices,
    generate_recommendations,
    calculate_price_stats_for_cluster,
)

__all__ = [
    # Models
    'Product', 'ProductSpecs', 'ProductCluster', 
    'PriceAnalysis', 'Recommendation', 'AnalysisConfig',
    'MatchLevel', 'ResultType',
    # Matcher
    'extract_specs_from_title', 'calculate_match_score',
    'calculate_text_similarity', 'cluster_products',
    'find_matching_products', 'identify_your_product',
    # Analyzer
    'analyze_prices', 'generate_recommendations',
    'calculate_price_stats_for_cluster',
]
