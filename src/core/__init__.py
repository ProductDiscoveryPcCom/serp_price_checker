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

from .token_matcher import (
    TokenMatch,
    MatchLevel,
    calculate_token_match,
    calculate_text_similarity,
    find_best_matches,
    cluster_by_brand,
    format_match_level,
    extract_tokens,
    KNOWN_BRANDS,
)

from .analyzer import (
    analyze_prices,
    generate_recommendations,
)

__all__ = [
    # Models
    'Product', 'ProductSpecs', 'ProductCluster', 
    'PriceAnalysis', 'Recommendation', 'AnalysisConfig',
    'MatchLevel', 'ResultType',
    # Token Matcher
    'TokenMatch', 'calculate_token_match', 'calculate_text_similarity',
    'find_best_matches', 'cluster_by_brand', 'format_match_level',
    'extract_tokens', 'KNOWN_BRANDS',
    # Analyzer
    'analyze_prices', 'generate_recommendations',
]
