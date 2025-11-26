"""Matching genérico de productos basado en tokens.

Funciona para cualquier tipo de producto, no solo portátiles.
Compara productos por palabras clave extraídas del título.
"""

import re
from difflib import SequenceMatcher
from typing import List, Set, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchLevel(Enum):
    """Nivel de coincidencia entre productos."""
    EXACT = "exact"           # Mismo producto (>90%)
    VERY_SIMILAR = "very_similar"  # Muy similar (75-90%)
    SIMILAR = "similar"       # Similar (50-75%)
    RELATED = "related"       # Relacionado (30-50%)
    DIFFERENT = "different"   # Diferente (<30%)


@dataclass
class TokenMatch:
    """Resultado del matching de tokens."""
    score: float                    # 0-1
    level: MatchLevel
    matched_tokens: Set[str]        # Tokens que coinciden
    unmatched_tokens: Set[str]      # Tokens que no coinciden
    brand_match: bool               # ¿Coincide la marca?
    model_match: bool               # ¿Coincide el modelo/SKU?


# Marcas conocidas (para dar más peso)
KNOWN_BRANDS = {
    # Tecnología
    'apple', 'iphone', 'ipad', 'macbook', 'airpods', 'imac',
    'samsung', 'galaxy',
    'xiaomi', 'redmi', 'poco',
    'huawei', 'honor',
    'sony', 'xperia', 'playstation', 'ps4', 'ps5',
    'lg', 'philips', 'panasonic',
    'asus', 'rog', 'tuf', 'zenfone',
    'acer', 'nitro', 'predator',
    'lenovo', 'thinkpad', 'ideapad', 'legion',
    'hp', 'omen', 'pavilion', 'envy',
    'dell', 'alienware', 'xps', 'inspiron',
    'msi', 'raider', 'stealth', 'cyborg', 'katana',
    'gigabyte', 'aorus', 'aero',
    'razer', 'blade',
    'logitech', 'corsair', 'steelseries', 'hyperx', 'trust', 'genius',
    'tp-link', 'netgear', 'dlink', 'd-link', 'ubiquiti', 'zyxel', 'linksys',
    'seagate', 'western digital', 'wd', 'sandisk', 'kingston', 'crucial', 'toshiba',
    'nvidia', 'geforce', 'rtx', 'gtx',
    'amd', 'radeon', 'ryzen',
    'intel', 'core',
    'canon', 'nikon', 'fujifilm', 'gopro', 'dji', 'insta360', 'osmo',
    'bose', 'jbl', 'harman', 'marshall', 'bang olufsen', 'sennheiser', 'audio technica',
    'braun', 'remington', 'babyliss', 'rowenta', 'tefal',
    # Gaming
    'nintendo', 'switch', 'xbox', 'microsoft', 'valve', 'steam', 'deck',
    'newskill', 'krom', 'tempest', 'mars gaming', 'nox', 'coolbox', 'ozone',
    'elgato', 'streamdeck',
    # Electrodomésticos
    'bosch', 'siemens', 'balay', 'teka', 'zanussi', 'electrolux', 'whirlpool', 'aeg',
    'cecotec', 'conga', 'mambo', 'bamba',
    'dyson', 'roomba', 'irobot', 'roborock', 'dreame', 'ecovacs',
    'delonghi', 'nespresso', 'krups', 'moulinex', 'smeg', 'kitchenaid',
    'daikin', 'mitsubishi', 'hisense', 'haier',
    # Movilidad
    'garmin', 'tomtom', 'fitbit', 'polar', 'suunto', 'coros',
    'segway', 'ninebot', 'youin', 'nilox', 'smartgyro',
    # Hogar/Jardín
    'ikea', 'leroy', 'bricomart',
    'gardena', 'makita', 'dewalt', 'black decker', 'stanley', 'einhell', 'parkside',
    # Retail
    'pccomponentes', 'pccom', 'pccm', 'amazon', 'mediamarkt', 'carrefour', 'fnac',
}

# Sinónimos para normalizar nombres
SYNONYMS = {
    'playstation': ['ps', 'ps4', 'ps5', 'psx', 'psone'],
    'ps5': ['playstation 5', 'playstation5', 'play station 5'],
    'ps4': ['playstation 4', 'playstation4', 'play station 4'],
    'nintendo switch': ['switch', 'ns', 'nswitch'],
    'xbox': ['xb', 'xbone', 'xboxone', 'xboxseries', 'xbx', 'xbs'],
    'iphone': ['apple iphone', 'i-phone'],
    'ipad': ['apple ipad', 'i-pad'],
    'macbook': ['apple macbook', 'mac book'],
    'airpods': ['apple airpods', 'air pods'],
    'galaxy': ['samsung galaxy'],
    'geforce': ['nvidia geforce', 'nvidia'],
    'radeon': ['amd radeon'],
    'ryzen': ['amd ryzen'],
    'core': ['intel core'],
    'roomba': ['irobot roomba'],
    'conga': ['cecotec conga'],
    'negro': ['black', 'noir', 'negra'],
    'blanco': ['white', 'blanc', 'blanca'],
    'gris': ['grey', 'gray', 'silver', 'plata'],
    'azul': ['blue', 'bleu'],
    'rojo': ['red', 'rouge'],
    'verde': ['green', 'vert'],
    'rosa': ['pink', 'rose'],
    'dorado': ['gold', 'golden', 'oro'],
    '256gb': ['256 gb', '256g'],
    '512gb': ['512 gb', '512g'],
    '1tb': ['1 tb', '1000gb', '1024gb'],
    '2tb': ['2 tb', '2000gb', '2048gb'],
}

# Palabras a ignorar (stop words)
STOP_WORDS = {
    'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'y', 'o', 'a', 'en', 'con', 'para', 'por', 'sin', 'sobre',
    'the', 'a', 'an', 'and', 'or', 'of', 'for', 'with', 'to', 'in', 'on',
    'es', 'eu', 'com', 'www', 'http', 'https',
    'nuevo', 'new', 'oficial', 'original', 'version', 'edicion', 'edition',
    'pack', 'kit', 'set', 'bundle', 'combo', 'lote',
}

# Patrones de modelo/SKU (números y códigos alfanuméricos)
MODEL_PATTERNS = [
    r'\b[A-Z]{2,}\d{3,}[A-Z]*\b',           # MSI123, AB1234CD
    r'\b[A-Z]\d{2}[A-Z]{2,}\d*\b',          # B13WFKG
    r'\b\d{4,}[A-Z]+\b',                     # 1234AB
    r'\b[A-Z]{1,3}-?\d{3,}[A-Z]*\b',        # PS-1234, A-123B
    r'\b[A-Z]{2,}\d+[-/][A-Z0-9]+\b',       # ABC12-34, XY1/2Z
    r'\b\d{2,}[A-Z]{2,}\d+\b',              # 15FA2018
]


def normalize_text(text: str) -> str:
    """Normaliza texto para comparación."""
    if not text:
        return ""
    # Minúsculas
    text = text.lower()
    # Reemplazar caracteres especiales
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    # Quitar caracteres no alfanuméricos excepto espacios
    text = re.sub(r'[^\w\s]', ' ', text)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def expand_with_synonyms(text: str) -> str:
    """Expande el texto añadiendo sinónimos."""
    text_lower = text.lower()
    expanded = text_lower
    
    for main_term, synonyms in SYNONYMS.items():
        # Si encontramos un sinónimo, añadimos el término principal
        for syn in synonyms:
            if syn in text_lower:
                expanded += f" {main_term}"
                break
        # Si encontramos el término principal, añadimos el primer sinónimo común
        if main_term in text_lower and synonyms:
            expanded += f" {synonyms[0]}"
    
    return expanded


def extract_tokens(title: str) -> Tuple[Set[str], Optional[str], Optional[str]]:
    """
    Extrae tokens significativos del título.
    
    Returns:
        (tokens, marca, modelo)
    """
    if not title:
        return set(), None, None
    
    # Expandir con sinónimos
    expanded = expand_with_synonyms(title)
    normalized = normalize_text(expanded)
    original_lower = title.lower()
    
    # Extraer marca (buscar en texto expandido)
    brand = None
    for known_brand in KNOWN_BRANDS:
        if known_brand in normalized:
            brand = known_brand
            break
    
    # Extraer modelo/SKU
    model = None
    for pattern in MODEL_PATTERNS:
        match = re.search(pattern, title.upper())
        if match:
            model = match.group(0)
            break
    
    # Tokenizar
    words = normalized.split()
    
    # Filtrar stop words y tokens muy cortos
    tokens = set()
    for word in words:
        if len(word) >= 2 and word not in STOP_WORDS:
            tokens.add(word)
    
    # Añadir números importantes (capacidades, tamaños, etc.)
    numbers = re.findall(r'\d+(?:[.,]\d+)?(?:\s*(?:gb|tb|mb|kg|g|l|ml|w|v|hz|mah|mm|cm|m|pulgadas))?', normalized)
    for num in numbers:
        if len(num) >= 2:
            tokens.add(num.replace(' ', ''))
    
    return tokens, brand, model


def calculate_token_match(
    product_title: str,
    reference_title: str,
    brand_weight: float = 0.25,
    model_weight: float = 0.35,
    token_weight: float = 0.40
) -> TokenMatch:
    """
    Calcula el matching entre dos productos basado en tokens.
    
    Args:
        product_title: Título del producto a comparar
        reference_title: Título del producto de referencia
        brand_weight: Peso de la marca (0-1)
        model_weight: Peso del modelo/SKU (0-1)
        token_weight: Peso de los tokens generales (0-1)
    
    Returns:
        TokenMatch con el resultado
    """
    # Extraer tokens
    p_tokens, p_brand, p_model = extract_tokens(product_title)
    r_tokens, r_brand, r_model = extract_tokens(reference_title)
    
    score = 0.0
    
    # 1. Comparar marca
    brand_match = False
    if p_brand and r_brand:
        brand_match = p_brand == r_brand
        if brand_match:
            score += brand_weight
    elif p_brand or r_brand:
        # Solo uno tiene marca detectada
        score += brand_weight * 0.2  # Pequeño bonus si al menos uno tiene marca
    
    # 2. Comparar modelo/SKU
    model_match = False
    if p_model and r_model:
        model_match = p_model.upper() == r_model.upper()
        if model_match:
            score += model_weight  # Match de modelo es muy importante
        else:
            # Comparar similitud parcial de modelo
            model_sim = SequenceMatcher(None, p_model.upper(), r_model.upper()).ratio()
            if model_sim > 0.7:
                score += model_weight * model_sim
    
    # 3. Comparar tokens generales
    matched_tokens = p_tokens & r_tokens
    all_tokens = p_tokens | r_tokens
    unmatched_tokens = all_tokens - matched_tokens
    
    if all_tokens:
        token_ratio = len(matched_tokens) / len(all_tokens)
        score += token_weight * token_ratio
    
    # 4. Bonus por números específicos que coinciden (capacidades, tamaños)
    p_numbers = set(re.findall(r'\d+', product_title))
    r_numbers = set(re.findall(r'\d+', reference_title))
    if p_numbers and r_numbers:
        number_match_ratio = len(p_numbers & r_numbers) / max(len(p_numbers), len(r_numbers))
        score += 0.1 * number_match_ratio  # Pequeño bonus extra
    
    # Normalizar score
    score = min(1.0, score)
    
    # Determinar nivel
    if model_match or score >= 0.90:
        level = MatchLevel.EXACT
    elif score >= 0.75:
        level = MatchLevel.VERY_SIMILAR
    elif score >= 0.50:
        level = MatchLevel.SIMILAR
    elif score >= 0.30:
        level = MatchLevel.RELATED
    else:
        level = MatchLevel.DIFFERENT
    
    return TokenMatch(
        score=score,
        level=level,
        matched_tokens=matched_tokens,
        unmatched_tokens=unmatched_tokens,
        brand_match=brand_match,
        model_match=model_match
    )


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calcula similitud de texto simple (0-100)."""
    if not text1 or not text2:
        return 0.0
    t1 = normalize_text(text1)
    t2 = normalize_text(text2)
    return SequenceMatcher(None, t1, t2).ratio() * 100


def find_best_matches(
    products: list,
    reference_title: str,
    min_score: float = 0.3,
    max_results: int = 50
) -> list:
    """
    Encuentra los productos que mejor coinciden con una referencia.
    
    Args:
        products: Lista de productos (deben tener atributo 'title')
        reference_title: Título del producto de referencia
        min_score: Score mínimo para incluir
        max_results: Máximo de resultados
    
    Returns:
        Lista de productos ordenados por score descendente
    """
    results = []
    
    for product in products:
        title = getattr(product, 'title', '') or ''
        if not title:
            continue
        
        match = calculate_token_match(title, reference_title)
        
        if match.score >= min_score:
            # Añadir info de match al producto
            product.match_score = match.score
            product.match_level = match.level
            product.brand_match = match.brand_match
            product.model_match = match.model_match
            results.append(product)
    
    # Ordenar por score
    results.sort(key=lambda x: x.match_score, reverse=True)
    
    return results[:max_results]


def cluster_by_brand(products: list) -> dict:
    """
    Agrupa productos por marca.
    
    Returns:
        Dict {marca: [productos]}
    """
    clusters = {}
    
    for product in products:
        title = getattr(product, 'title', '') or ''
        _, brand, _ = extract_tokens(title)
        
        brand_key = brand or 'otras'
        
        if brand_key not in clusters:
            clusters[brand_key] = []
        clusters[brand_key].append(product)
    
    return clusters


def format_match_level(level: MatchLevel, score: float) -> str:
    """Formatea nivel de match para UI."""
    if level == MatchLevel.EXACT:
        return "✅ Exacto"
    elif level == MatchLevel.VERY_SIMILAR:
        return f"🔷 Muy similar ({score*100:.0f}%)"
    elif level == MatchLevel.SIMILAR:
        return f"🔶 Similar ({score*100:.0f}%)"
    elif level == MatchLevel.RELATED:
        return f"🟡 Relacionado ({score*100:.0f}%)"
    else:
        return f"⚪ Diferente ({score*100:.0f}%)"


# === TESTS ===
if __name__ == "__main__":
    # Test con diferentes tipos de productos
    tests = [
        # Portátiles (caso original)
        ("MSI Cyborg 15 B13WFKG-687XES Intel Core i7-13620H 16GB 1TB SSD RTX 4060",
         "MSI Cyborg 15 B13WFKG-687XES 16GB 1TB RTX 4060 15.6\" FHD"),
        
        # Móviles
        ("Samsung Galaxy S24 Ultra 256GB Negro",
         "Samsung Galaxy S24 Ultra 256GB Titanium Black"),
        
        # Electrodomésticos
        ("Cecotec Conga 9090 IA Robot Aspirador",
         "Cecotec Conga 9090 Robot Aspirador Láser"),
        
        # Consolas
        ("Sony PlayStation 5 Digital Edition",
         "PS5 Digital Edition Blanca"),
        
        # Accesorios genéricos
        ("Funda Silicona iPhone 15 Pro Max Negra",
         "Funda iPhone 15 Pro Max Silicona Negro"),
         
        # Productos muy diferentes
        ("MSI Cyborg 15 Gaming",
         "Cecotec Conga 9090 Robot"),
    ]
    
    print("=== Tests de matching genérico ===\n")
    
    for t1, t2 in tests:
        match = calculate_token_match(t1, t2)
        print(f"Producto 1: {t1[:50]}...")
        print(f"Producto 2: {t2[:50]}...")
        print(f"  Score: {match.score:.2f}")
        print(f"  Level: {match.level.value}")
        print(f"  Marca: {'✅' if match.brand_match else '❌'}")
        print(f"  Modelo: {'✅' if match.model_match else '❌'}")
        print(f"  Tokens comunes: {match.matched_tokens}")
        print()
