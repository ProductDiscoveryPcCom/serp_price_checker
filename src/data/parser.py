"""Parser de datos CSV y SERP."""

import re
import csv
import io
import logging
from typing import List, Tuple, Optional
from ..core.models import Product, ProductSpecs, ResultType
from ..core.matcher import extract_specs_from_title

logger = logging.getLogger(__name__)

# Tipos válidos de la extensión Chrome
VALID_TYPES = {'Shopping Ads', 'Organic', 'Ads', 'Ads Sub'}

# Dominios a filtrar (comparadores, CSS partners)
SKIP_DOMAINS = [
    'kelkoo', 'idealo', 'shopping.com', 'shoparize', 
    'producthero', 'delupe', 'adference', 'klarna',
    'redbrain', 'surferseo', 'google.com', 'docs.surferseo',
    'pricerunner', 'twenga', 'shopmania', 'ciao'
]


def parse_price_from_text(text: str) -> Tuple[float, Optional[float], bool]:
    """
    Extrae precio(s) de un texto.
    
    Maneja múltiples formatos:
    - "94900 €" = 949.00€ (5+ dígitos = céntimos)
    - "599 €" = 599.00€ (3-4 dígitos = euros)
    - "1.299,00 €" = 1299.00€ (formato español)
    - "Oferta47900 €599 €" = actual: 479€, original: 599€
    
    Returns:
        (precio_actual, precio_original, es_oferta)
    """
    if not text:
        return (0.0, None, False)
    
    is_offer = bool(re.search(r'oferta', text, re.IGNORECASE))
    
    # Buscar precios en diferentes formatos
    prices = []
    
    # Formato 1: números de 5-6 dígitos seguidos de € (céntimos)
    for match in re.finditer(r'(\d{5,6})\s*€', text):
        num = int(match.group(1))
        prices.append(num / 100)
    
    # Formato 2: números de 3-4 dígitos seguidos de € (euros)
    for match in re.finditer(r'(?<!\d)(\d{3,4})\s*€', text):
        num = int(match.group(1))
        # Verificar que no es parte de un número más largo
        start = match.start()
        if start > 0 and text[start-1].isdigit():
            continue
        prices.append(float(num))
    
    # Formato 3: formato español "1.299,00 €"
    for match in re.finditer(r'(\d{1,3}(?:\.\d{3})*),(\d{2})\s*€', text):
        num_str = match.group(1).replace('.', '') + '.' + match.group(2)
        prices.append(float(num_str))
    
    # Eliminar duplicados y ordenar
    prices = sorted(set(prices))
    
    if not prices:
        return (0.0, None, False)
    
    if len(prices) == 1:
        return (prices[0], None, is_offer)
    
    # Si hay múltiples precios, el menor suele ser el actual
    current = prices[0]
    original = prices[-1] if prices[-1] != current else None
    
    # Verificar que el original sea mayor (tiene sentido como descuento)
    if original and original <= current:
        original = None
    
    return (current, original, is_offer or original is not None)


def clean_product_title(anchor: str) -> str:
    """Extrae título limpio del anchor text."""
    if not anchor:
        return ""
    
    title = anchor
    
    # Quitar "Oferta" al inicio
    title = re.sub(r'^Oferta\s*', '', title, flags=re.IGNORECASE)
    
    # Quitar duplicados comunes
    title = re.sub(r'^Portátil\s+Portátil\s+', 'Portátil ', title, flags=re.IGNORECASE)
    
    # Cortar donde empieza el precio
    price_match = re.search(r'\d{3,6}\s*€', title)
    if price_match:
        title = title[:price_match.start()]
    
    # Quitar información de envío/tienda al final
    title = re.sub(r'(Sin coste|Envío gratis|En stock).*$', '', title, flags=re.IGNORECASE)
    
    return title.strip()


def parse_extension_csv(csv_content: str) -> List[Product]:
    """
    Parsea el CSV de la extensión Google Rank Checker.
    
    Args:
        csv_content: Contenido del CSV como string
        
    Returns:
        Lista de productos parseados
    """
    products = []
    seen_urls = set()
    errors = 0
    
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
    except Exception as e:
        logger.error(f"Error leyendo CSV: {e}")
        return products
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
        try:
            csv_type = row.get('Type', '').strip()
            domain = row.get('Domain', '').strip()
            link = row.get('Link', '').strip()
            anchor = row.get('Anchor', '').strip()
            rank = row.get('Rank', '0').strip()
            
            # Validaciones básicas
            if not anchor or not domain or not link:
                continue
            
            # Solo tipos válidos
            if csv_type not in VALID_TYPES:
                continue
            
            # Evitar duplicados
            if link in seen_urls:
                continue
            seen_urls.add(link)
            
            # Filtrar comparadores
            domain_lower = domain.lower()
            if any(skip in domain_lower for skip in SKIP_DOMAINS):
                continue
            
            # Extraer precios
            current_price, original_price, is_offer = parse_price_from_text(anchor)
            
            # Extraer título
            title = clean_product_title(anchor)
            
            # Para resultados sin precio (Organic/Ads), usar anchor limpio
            if not title or len(title) < 5:
                # Limpiar anchor de URLs
                title = anchor.split('https://')[0].split('http://')[0]
                title = re.sub(r'[a-zA-Z]+\.[a-z]{2,3}(?:/|https?).*', '', title)
                title = title.strip()
            
            if not title or len(title) < 5:
                continue
            
            # Extraer especificaciones
            specs = extract_specs_from_title(title) if current_price > 0 else ProductSpecs()
            
            # Crear producto
            product = Product(
                title=title,
                store=domain.replace('www.', ''),
                url=link,
                price=current_price,
                original_price=original_price,
                is_offer=is_offer,
                result_type=csv_type,
                rank=int(rank) if rank.isdigit() else 0,
                specs=specs,
            )
            
            products.append(product)
            
        except Exception as e:
            errors += 1
            logger.warning(f"Error en fila {row_num}: {e}")
            continue
    
    if errors > 0:
        logger.info(f"Parseado completado con {errors} errores en {len(products) + errors} filas")
    
    # Ordenar: primero con precio, luego por precio
    products.sort(key=lambda x: (not x.has_price, x.price if x.has_price else float('inf')))
    
    return products


def group_products_by_type(products: List[Product]) -> dict:
    """Agrupa productos por tipo de resultado."""
    groups = {
        "Shopping Ads": [],
        "Organic": [],
        "Ads": [],
        "Ads Sub": [],
    }
    
    for p in products:
        if p.result_type in groups:
            groups[p.result_type].append(p)
    
    return groups


def group_products_by_store(products: List[Product]) -> dict:
    """Agrupa productos por tienda."""
    stores = {}
    for p in products:
        store = p.store or "Desconocida"
        if store not in stores:
            stores[store] = []
        stores[store].append(p)
    return stores


def get_price_distribution(products: List[Product], bins: int = 10) -> List[dict]:
    """Calcula distribución de precios para gráfico."""
    prices = [p.price for p in products if p.has_price]
    
    if not prices:
        return []
    
    min_price = min(prices)
    max_price = max(prices)
    
    if min_price == max_price:
        return [{"range": f"{min_price:.0f}€", "count": len(prices)}]
    
    bin_size = (max_price - min_price) / bins
    distribution = []
    
    for i in range(bins):
        low = min_price + (i * bin_size)
        high = min_price + ((i + 1) * bin_size)
        count = len([p for p in prices if low <= p < high])
        
        distribution.append({
            "range": f"{low:.0f}-{high:.0f}€",
            "low": low,
            "high": high,
            "count": count
        })
    
    return distribution
