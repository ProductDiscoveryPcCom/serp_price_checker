"""Matching inteligente de productos por especificaciones."""

import re
from difflib import SequenceMatcher
from typing import Optional, List, Dict
from .models import Product, ProductSpecs, MatchLevel, ProductCluster


# Mapeo de GPU a tiers
GPU_TIERS = {
    "RTX 5090": "RTX 50xx",
    "RTX 5080": "RTX 50xx", 
    "RTX 5070": "RTX 50xx",
    "RTX 5060": "RTX 50xx",
    "RTX 5050": "RTX 50xx",
    "RTX 4090": "RTX 40xx",
    "RTX 4080": "RTX 40xx",
    "RTX 4070": "RTX 40xx",
    "RTX 4060": "RTX 40xx",
    "RTX 4050": "RTX 40xx",
    "RTX 3080": "RTX 30xx",
    "RTX 3070": "RTX 30xx",
    "RTX 3060": "RTX 30xx",
    "RTX 3050": "RTX 30xx",
    "RTX 2080": "RTX 20xx",
    "RTX 2070": "RTX 20xx",
    "RTX 2060": "RTX 20xx",
    "RTX 2050": "RTX 20xx",
    "GTX 1660": "GTX 16xx",
    "GTX 1650": "GTX 16xx",
}

# Series de productos por marca
PRODUCT_SERIES = {
    "MSI": ["Cyborg", "Thin", "Modern", "Stealth", "Raider", "Titan", "Katana", "Pulse", "Vector", "Crosshair"],
    "ASUS": ["ROG", "TUF", "Zephyrus", "Strix", "ProArt", "Zenbook", "Vivobook"],
    "ACER": ["Nitro", "Predator", "Aspire", "Swift", "Triton"],
    "LENOVO": ["Legion", "IdeaPad", "ThinkPad", "Yoga", "LOQ"],
    "HP": ["Omen", "Victus", "Pavilion", "Envy", "Spectre"],
    "DELL": ["Alienware", "G15", "G16", "XPS", "Inspiron"],
    "GIGABYTE": ["Aorus", "Aero", "G5", "G7"],
}


def extract_specs_from_title(title: str) -> ProductSpecs:
    """Extrae especificaciones técnicas del título del producto."""
    specs = ProductSpecs()
    title_lower = title.lower()
    title_upper = title.upper()
    
    # === MARCA ===
    brands = ['MSI', 'ASUS', 'ACER', 'LENOVO', 'HP', 'DELL', 'GIGABYTE', 'RAZER', 'ALIENWARE']
    for brand in brands:
        if brand.lower() in title_lower:
            specs.brand = brand
            break
    
    # === SERIE ===
    if specs.brand and specs.brand in PRODUCT_SERIES:
        for series in PRODUCT_SERIES[specs.brand]:
            if series.lower() in title_lower:
                specs.series = series
                break
    
    # === MODELO (código SKU) ===
    model_patterns = [
        r'([A-Z]\d{2}[A-Z]{2,}[-_]?\d{3,}[A-Z]*)',  # B13WFKG-687XES
        r'([A-Z]{2,}\d{2,}[-_][A-Z0-9]+)',           # ANV15-51-579P
        r'(\d{2}[A-Z]{2}\d+[-_]\d+[A-Z]*)',          # 15FA2018NS
    ]
    for pattern in model_patterns:
        match = re.search(pattern, title_upper)
        if match:
            specs.model_code = match.group(1)
            break
    
    # === PROCESADOR ===
    # Intel Core i series
    intel_match = re.search(r'(i[357]-?\d{4,5}[A-Z]*)', title_lower)
    if intel_match:
        specs.processor = f"Intel Core {intel_match.group(1).upper()}"
        # Detectar generación
        proc_num = re.search(r'i[357]-?(\d)', intel_match.group(1))
        if proc_num:
            gen = proc_num.group(1)
            if gen in ['1', '2']:
                specs.processor_gen = f"{gen}th Gen" if int(gen) > 1 else "1st Gen"
            else:
                specs.processor_gen = f"{gen}th Gen"
    
    # Intel Core (nueva nomenclatura: Core 5, Core 7)
    if not specs.processor:
        core_match = re.search(r'core\s+([57])\s*[-_]?\s*(\d{3}[A-Z]*)', title_lower)
        if core_match:
            specs.processor = f"Intel Core {core_match.group(1)} {core_match.group(2).upper()}"
            specs.processor_gen = "Ultra"
    
    # AMD Ryzen
    if not specs.processor:
        amd_match = re.search(r'ryzen\s*([357])\s*[-_]?\s*(\d{4}[A-Z]*)', title_lower)
        if amd_match:
            specs.processor = f"AMD Ryzen {amd_match.group(1)} {amd_match.group(2).upper()}"
            ryzen_num = amd_match.group(2)[0]
            specs.processor_gen = f"Ryzen {ryzen_num}000"
    
    # === RAM ===
    ram_patterns = [
        r'(\d{1,2})\s*gb\s*(?:ram|ddr)',
        r'(\d{1,2})\s*gb(?!\s*ssd)',
    ]
    for pattern in ram_patterns:
        ram_match = re.search(pattern, title_lower)
        if ram_match:
            gb = int(ram_match.group(1))
            if gb in [8, 16, 32, 64, 128]:
                specs.ram_gb = gb
                break
    
    # === ALMACENAMIENTO ===
    storage_match = re.search(r'(\d+)\s*(tb|gb)\s*ssd', title_lower)
    if storage_match:
        amount = int(storage_match.group(1))
        unit = storage_match.group(2)
        specs.storage_gb = amount * 1000 if unit == 'tb' else amount
        specs.storage_type = "SSD"
    
    # === GPU ===
    gpu_patterns = [
        (r'rtx\s*(\d{4})', 'RTX'),
        (r'gtx\s*(\d{4})', 'GTX'),
        (r'geforce\s*(rtx|gtx)\s*(\d{4})', None),
        (r'radeon\s*rx\s*(\d{4})', 'RX'),
    ]
    for pattern, prefix in gpu_patterns:
        gpu_match = re.search(pattern, title_lower)
        if gpu_match:
            if prefix:
                specs.gpu = f"{prefix} {gpu_match.group(1)}"
            else:
                specs.gpu = f"{gpu_match.group(1).upper()} {gpu_match.group(2)}"
            break
    
    # GPU Tier
    if specs.gpu:
        for gpu_name, tier in GPU_TIERS.items():
            if gpu_name.lower() in specs.gpu.lower():
                specs.gpu_tier = tier
                break
    
    # === PANTALLA ===
    screen_match = re.search(r'(\d{2})[.,]?(\d)?\s*["\']', title_lower)
    if screen_match:
        size = screen_match.group(1)
        decimal = screen_match.group(2) or "0"
        specs.screen_size = float(f"{size}.{decimal}")
    
    # Resolución
    if 'full hd' in title_lower or 'fhd' in title_lower or '1080' in title_lower:
        specs.screen_resolution = "FHD"
    elif 'qhd' in title_lower or '1440' in title_lower or '2k' in title_lower:
        specs.screen_resolution = "QHD"
    elif '4k' in title_lower or 'uhd' in title_lower or '2160' in title_lower:
        specs.screen_resolution = "4K"
    elif 'wuxga' in title_lower:
        specs.screen_resolution = "WUXGA"
    
    # Hz
    hz_match = re.search(r'(\d{2,3})\s*hz', title_lower)
    if hz_match:
        specs.screen_hz = int(hz_match.group(1))
    
    # === SISTEMA OPERATIVO ===
    if 'windows 11' in title_lower:
        specs.os = "Windows 11"
    elif 'windows 10' in title_lower:
        specs.os = "Windows 10"
    elif 'freedos' in title_lower or 'free dos' in title_lower:
        specs.os = "FreeDOS"
    elif 'sin sistema' in title_lower or 'no os' in title_lower:
        specs.os = "Sin SO"
    
    return specs


def calculate_match_score(product: Product, reference: Product) -> tuple[float, MatchLevel]:
    """
    Calcula el score de coincidencia entre dos productos.
    
    Returns:
        (score 0-1, nivel de match)
    """
    p1 = product.specs
    p2 = reference.specs
    
    # Si tienen el mismo código de modelo = EXACTO
    if p1.model_code and p2.model_code:
        if p1.model_code.upper() == p2.model_code.upper():
            return (1.0, MatchLevel.EXACT)
    
    score = 0.0
    max_score = 0.0
    
    # Marca (peso: 0.15)
    max_score += 0.15
    if p1.brand and p2.brand and p1.brand.upper() == p2.brand.upper():
        score += 0.15
    
    # Serie (peso: 0.15) - Cyborg vs Thin es diferente
    max_score += 0.15
    if p1.series and p2.series:
        if p1.series.upper() == p2.series.upper():
            score += 0.15
        elif p1.brand == p2.brand:
            score += 0.05  # Misma marca, diferente serie
    
    # GPU Tier (peso: 0.25) - RTX 50xx vs RTX 30xx es muy diferente
    max_score += 0.25
    if p1.gpu_tier and p2.gpu_tier:
        if p1.gpu_tier == p2.gpu_tier:
            score += 0.25
        elif p1.gpu and p2.gpu:
            # Misma familia pero diferente tier
            score += 0.10
    elif p1.gpu and p2.gpu:
        if p1.gpu.upper() == p2.gpu.upper():
            score += 0.25
    
    # Procesador generación (peso: 0.15)
    max_score += 0.15
    if p1.processor_gen and p2.processor_gen:
        if p1.processor_gen == p2.processor_gen:
            score += 0.15
        else:
            score += 0.05  # Diferente generación
    elif p1.processor and p2.processor:
        if p1.processor.upper() == p2.processor.upper():
            score += 0.15
    
    # RAM (peso: 0.15)
    max_score += 0.15
    if p1.ram_gb and p2.ram_gb:
        if p1.ram_gb == p2.ram_gb:
            score += 0.15
        elif abs(p1.ram_gb - p2.ram_gb) <= 8:
            score += 0.08  # Diferencia de 8GB o menos
    
    # Almacenamiento (peso: 0.10)
    max_score += 0.10
    if p1.storage_gb and p2.storage_gb:
        if p1.storage_gb == p2.storage_gb:
            score += 0.10
        elif abs(p1.storage_gb - p2.storage_gb) <= 512:
            score += 0.05
    
    # Pantalla (peso: 0.05)
    max_score += 0.05
    if p1.screen_size and p2.screen_size:
        if abs(p1.screen_size - p2.screen_size) < 0.5:
            score += 0.05
    
    # Normalizar
    final_score = score / max_score if max_score > 0 else 0
    
    # Determinar nivel
    if final_score >= 0.90:
        level = MatchLevel.EXACT
    elif final_score >= 0.70:
        level = MatchLevel.EQUIVALENT
    elif final_score >= 0.50:
        level = MatchLevel.SIMILAR
    else:
        level = MatchLevel.DIFFERENT
    
    return (final_score, level)


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calcula similitud de texto (método legacy)."""
    if not text1 or not text2:
        return 0.0
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    return SequenceMatcher(None, t1, t2).ratio() * 100


def cluster_products(products: List[Product]) -> List[ProductCluster]:
    """
    Agrupa productos por especificaciones similares.
    
    Productos del mismo cluster son comparables entre sí.
    """
    clusters: Dict[str, ProductCluster] = {}
    
    for product in products:
        if not product.has_price:
            continue
        
        # Generar clave de cluster
        key = product.specs.get_tier_key()
        
        # Nombre legible del cluster
        parts = []
        if product.specs.brand:
            parts.append(product.specs.brand)
        if product.specs.series:
            parts.append(product.specs.series)
        if product.specs.gpu_tier:
            parts.append(product.specs.gpu_tier)
        elif product.specs.gpu:
            parts.append(product.specs.gpu)
        
        name = " ".join(parts) if parts else "Otros"
        
        if key not in clusters:
            clusters[key] = ProductCluster(key=key, name=name, products=[])
        
        clusters[key].products.append(product)
    
    # Ordenar clusters por número de productos
    sorted_clusters = sorted(clusters.values(), key=lambda c: len(c.products), reverse=True)
    
    return sorted_clusters


def find_matching_products(
    products: List[Product],
    reference: Product,
    min_score: float = 0.5
) -> List[Product]:
    """Encuentra productos que coinciden con una referencia."""
    matches = []
    
    for product in products:
        if product.url == reference.url:
            continue
        
        score, level = calculate_match_score(product, reference)
        
        if score >= min_score:
            product.match_score = score
            product.match_level = level
            matches.append(product)
    
    # Ordenar por score descendente
    matches.sort(key=lambda x: x.match_score, reverse=True)
    
    return matches


def identify_your_product(
    products: List[Product],
    your_domain: str,
    your_price: Optional[float] = None
) -> Optional[Product]:
    """
    Identifica cuál de los productos es el tuyo.
    
    Criterios:
    1. Dominio coincide
    2. Si hay múltiples, el más cercano a tu precio
    """
    your_domain_clean = your_domain.lower().replace('www.', '')
    
    candidates = []
    for p in products:
        store_lower = p.store.lower() if p.store else ""
        url_lower = p.url.lower() if p.url else ""
        
        if your_domain_clean in store_lower or your_domain_clean in url_lower:
            candidates.append(p)
    
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    # Múltiples productos de tu tienda: elegir el más cercano a tu precio
    if your_price and your_price > 0:
        candidates.sort(key=lambda p: abs(p.price - your_price) if p.price else float('inf'))
    
    return candidates[0]
