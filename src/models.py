from dataclasses import dataclass, field
from typing import Optional, List, Any


@dataclass
class ShoppingResult:
    """Resultado de shopping/producto."""
    position: int
    title: str
    price: float
    store: str
    url: str = ""
    # Campos opcionales para características
    result_type: str = ""
    similarity: float = 0.0
    original_price: Optional[float] = None
    is_offer: bool = False
    # Características del producto
    brand: str = ""
    model: str = ""
    processor: str = ""
    ram: str = ""
    storage: str = ""
    gpu: str = ""
    screen: str = ""
    os: str = ""


@dataclass
class PriceAnalysis:
    """Análisis completo de precios."""
    query: str
    your_domain: str
    your_price: float
    your_serp_position: Optional[int]
    your_price_position: int
    total_competitors: int
    cheapest_competitor: Optional[ShoppingResult]
    most_expensive_competitor: Optional[ShoppingResult]
    average_price: Optional[float]
    all_results: List[ShoppingResult] = field(default_factory=list)


@dataclass
class StoreProducts:
    """Productos de una tienda específica."""
    store: str
    products: List[ShoppingResult] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return len(self.products)
    
    @property
    def cheapest(self) -> Optional[ShoppingResult]:
        if not self.products:
            return None
        return min(self.products, key=lambda x: x.price)
    
    @property
    def most_expensive(self) -> Optional[ShoppingResult]:
        if not self.products:
            return None
        return max(self.products, key=lambda x: x.price)
