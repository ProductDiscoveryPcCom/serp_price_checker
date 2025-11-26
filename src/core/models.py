"""Modelos de datos para SERP Price Checker."""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class MatchLevel(Enum):
    """Nivel de coincidencia entre productos."""
    EXACT = "exact"           # Mismo producto (>90%)
    VERY_SIMILAR = "very_similar"  # Muy similar (75-90%)
    SIMILAR = "similar"       # Similar (50-75%)
    RELATED = "related"       # Relacionado (30-50%)
    DIFFERENT = "different"   # Diferente (<30%)


class ResultType(Enum):
    """Tipo de resultado en SERP."""
    SHOPPING_ADS = "Shopping Ads"
    ORGANIC = "Organic"
    ADS = "Ads"
    ADS_SUB = "Ads Sub"


@dataclass
class ProductSpecs:
    """Especificaciones técnicas de un producto."""
    brand: str = ""
    series: str = ""          # Cyborg, Thin, Modern, Nitro...
    model_code: str = ""      # B13WFKG-687XES
    processor: str = ""
    processor_gen: str = ""   # 12th, 13th, Ryzen 7000...
    ram_gb: int = 0
    storage_gb: int = 0
    storage_type: str = ""    # SSD, HDD
    gpu: str = ""
    gpu_tier: str = ""        # RTX 50xx, RTX 40xx, RTX 30xx...
    screen_size: float = 0.0
    screen_resolution: str = ""
    screen_hz: int = 0
    os: str = ""
    
    def get_tier_key(self) -> str:
        """Genera clave para agrupar productos similares."""
        return f"{self.brand}_{self.series}_{self.gpu_tier}_{self.processor_gen}"
    
    def get_exact_key(self) -> str:
        """Genera clave para identificar producto exacto."""
        if self.model_code:
            return f"{self.brand}_{self.model_code}"
        return f"{self.brand}_{self.series}_{self.processor}_{self.gpu}_{self.ram_gb}GB"


@dataclass
class Product:
    """Producto con toda su información."""
    # Identificación
    title: str
    store: str
    url: str
    
    # Precio
    price: float
    original_price: Optional[float] = None
    is_offer: bool = False
    
    # Tipo de resultado
    result_type: str = "Shopping Ads"
    rank: int = 0
    
    # Matching
    match_level: MatchLevel = MatchLevel.DIFFERENT
    match_score: float = 0.0
    similarity_text: float = 0.0  # Similitud de texto (legacy)
    
    # Análisis
    price_diff_pct: float = 0.0
    price_diff_abs: float = 0.0
    is_your_product: bool = False
    
    @property
    def has_price(self) -> bool:
        return self.price > 0
    
    @property
    def discount_pct(self) -> Optional[float]:
        if self.original_price and self.original_price > self.price:
            return ((self.original_price - self.price) / self.original_price) * 100
        return None


@dataclass
class ProductCluster:
    """Grupo de productos equivalentes."""
    key: str
    name: str
    products: List[Product] = field(default_factory=list)
    
    @property
    def cheapest(self) -> Optional[Product]:
        priced = [p for p in self.products if p.has_price]
        return min(priced, key=lambda x: x.price) if priced else None
    
    @property
    def most_expensive(self) -> Optional[Product]:
        priced = [p for p in self.products if p.has_price]
        return max(priced, key=lambda x: x.price) if priced else None
    
    @property
    def avg_price(self) -> float:
        priced = [p for p in self.products if p.has_price]
        return sum(p.price for p in priced) / len(priced) if priced else 0
    
    @property
    def price_range(self) -> tuple[float, float]:
        priced = [p for p in self.products if p.has_price]
        if not priced:
            return (0, 0)
        prices = [p.price for p in priced]
        return (min(prices), max(prices))


@dataclass
class Recommendation:
    """Recomendación accionable."""
    type: str           # price_reduction, price_increase, opportunity, alert
    priority: str       # high, medium, low
    title: str
    description: str
    action: str
    impact: str
    data: dict = field(default_factory=dict)


@dataclass
class PriceAnalysis:
    """Análisis completo de precios."""
    query: str
    your_domain: str
    your_price: float
    your_product: Optional[Product] = None
    
    # Posiciones
    your_serp_position: Optional[int] = None
    your_price_rank: int = 0
    your_price_rank_in_cluster: int = 0
    
    # Estadísticas generales
    total_products: int = 0
    total_with_price: int = 0
    total_stores: int = 0
    
    # Estadísticas de precio
    min_price: float = 0
    max_price: float = 0
    avg_price: float = 0
    median_price: float = 0
    
    # Competidores
    cheapest: Optional[Product] = None
    products_cheaper: int = 0
    products_same: int = 0
    products_expensive: int = 0
    
    # Clusters
    clusters: List[ProductCluster] = field(default_factory=list)
    your_cluster: Optional[ProductCluster] = None
    
    # Productos
    all_products: List[Product] = field(default_factory=list)
    your_store_products: List[Product] = field(default_factory=list)
    exact_matches: List[Product] = field(default_factory=list)
    
    # Recomendaciones
    recommendations: List[Recommendation] = field(default_factory=list)


@dataclass 
class AnalysisConfig:
    """Configuración del análisis."""
    your_domain: str
    your_price: float
    your_product_url: Optional[str] = None
    product_query: str = ""
    
    # Matching
    match_by_specs: bool = True
    min_similarity: float = 60.0
    
    # Filtros
    exclude_comparators: bool = True
    only_with_price: bool = False
    
    # LLM
    use_llm: bool = False
    llm_provider: str = "default"
