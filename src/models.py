from dataclasses import dataclass
from typing import Optional


@dataclass
class SERPResult:
    """Representa un resultado orgánico de la SERP."""
    position: int
    title: str
    url: str
    domain: str
    snippet: str
    price: Optional[float] = None
    price_raw: Optional[str] = None


@dataclass
class ShoppingResult:
    """Representa un producto del carrusel de Google Shopping."""
    position: int
    title: str
    price: Optional[float]
    store: str
    url: Optional[str] = None


@dataclass
class MatchedProduct:
    """Producto con precio extraído."""
    title: str
    price: float
    store: str
    url: str = ""
    match_confidence: float = 0.9


@dataclass
class CompetitorAnalysis:
    """Resultado final del análisis."""
    query: str
    your_domain: str
    your_price: float
    competitors: list  # ShoppingResult o MatchedProduct
    your_serp_position: Optional[int] = None
    your_price_position: Optional[int] = None
    total_organic_results: int = 0
