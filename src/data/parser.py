"""Parser de datos CSV de la extensión Google Rank Checker."""

import re
import csv
import io
import logging
from typing import List, Tuple, Optional, Dict
from ..core.models import Product

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
    
    Formatos soportados:
    - "94900 €" = 949.00€ (5-6 dígitos sin separador = céntimos)
    - "599 €" = 599.00€ (3-4 dígitos = euros enteros)
    - "1.299,00 €" = 1299.00€ (español: punto miles, coma decimal)
    - "1,299.00 €" = 1299.00€ (americano: coma miles, punto decimal)
    - "599,99 €" = 599.99€ (europeo: coma decimal)
    - "599.99 €" = 599.99€ (americano: punto decimal)
    - "Oferta47900 €599 €" = actual: 479€, original: 599€
    
    Returns:
        (precio_actual, precio_original, es_oferta)
    """
    if not text:
        return (0.0, None, False)
    
    is_offer = bool(re.search(r'oferta', text, re.IGNORECASE))
    
    prices = []
    used_positions = set()  # Para evitar detectar el mismo precio dos veces
    
    # Formato 1: español con miles "1.299,00 €" o "1.299,99€"
    for match in re.finditer(r'(\d{1,3}(?:\.\d{3})+),(\d{2})\s*€', text):
        num_str = match.group(1).replace('.', '') + '.' + match.group(2)
        prices.append((float(num_str), match.start(), match.end()))
        used_positions.update(range(match.start(), match.end()))
    
    # Formato 2: americano con miles "1,299.00 €"
    for match in re.finditer(r'(\d{1,3}(?:,\d{3})+)\.(\d{2})\s*€', text):
        if match.start() not in used_positions:
            num_str = match.group(1).replace(',', '') + '.' + match.group(2)
            prices.append((float(num_str), match.start(), match.end()))
            used_positions.update(range(match.start(), match.end()))
    
    # Formato 3: europeo simple "599,99 €" (coma decimal, sin miles)
    for match in re.finditer(r'(\d{1,4}),(\d{2})\s*€', text):
        if match.start() not in used_positions:
            num_str = match.group(1) + '.' + match.group(2)
            prices.append((float(num_str), match.start(), match.end()))
            used_positions.update(range(match.start(), match.end()))
    
    # Formato 4: americano simple "599.99 €" (punto decimal)
    for match in re.finditer(r'(\d{1,4})\.(\d{2})\s*€', text):
        if match.start() not in used_positions:
            num_str = match.group(1) + '.' + match.group(2)
            prices.append((float(num_str), match.start(), match.end()))
            used_positions.update(range(match.start(), match.end()))
    
    # Formato 5: céntimos (5-6 dígitos seguidos de €, sin separador)
    for match in re.finditer(r'(\d{5,6})\s*€', text):
        if match.start() not in used_positions:
            num = int(match.group(1))
            prices.append((num / 100, match.start(), match.end()))
            used_positions.update(range(match.start(), match.end()))
    
    # Formato 6: euros enteros (3-4 dígitos seguidos de €)
    for match in re.finditer(r'(?<![.,\d])(\d{3,4})\s*€', text):
        if match.start() not in used_positions:
            prices.append((float(match.group(1)), match.start(), match.end()))
    
    # Extraer solo los valores de precio y filtrar
    # Filtro: 10€ mínimo, 10000€ máximo (productos muy caros probablemente son errores)
    price_values = sorted(set([p[0] for p in prices if 10 < p[0] < 10000]))
    
    if not price_values:
        return (0.0, None, False)
    
    if len(price_values) == 1:
        return (price_values[0], None, is_offer)
    
    # Si hay múltiples precios, el menor suele ser el actual (precio de oferta)
    current = price_values[0]
    original = price_values[-1] if price_values[-1] != current else None
    
    # Verificar que el original sea mayor
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
    
    # Quitar duplicados tipo "Portátil Portátil"
    words = title.split()
    if len(words) >= 2 and words[0].lower() == words[1].lower():
        title = ' '.join(words[1:])
    
    # Cortar donde empieza el precio (números + €)
    # Buscar patrón de precio
    price_match = re.search(r'\d{3,6}\s*€', title)
    if price_match:
        title = title[:price_match.start()]
    
    # Quitar info de envío/tienda al final
    patterns_to_remove = [
        r'Sin coste.*$',
        r'Envío.*$',
        r'Gratis.*$',
        r'\d+\s*días.*$',
        r'[A-Z][a-z]+\s*(ES|España)?\s*$',  # Nombres de tienda
    ]
    for pattern in patterns_to_remove:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    return title.strip()


def parse_extension_csv(csv_content: str) -> List[Product]:
    """
    Parsea CSV de la extensión Google Rank Checker.
    
    Formato esperado:
    Sr.,Rank,Type,Domain,Link,Anchor,Date,Query,Device,Location
    
    Returns:
        Lista de productos parseados
    """
    products = []
    seen_urls = set()
    errors = 0
    
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
    except Exception as e:
        logger.error(f"Error al parsear CSV: {e}")
        return []
    
    for row_num, row in enumerate(reader, 2):
        try:
            csv_type = row.get('Type', '').strip()
            
            # Filtrar tipos no válidos
            if csv_type not in VALID_TYPES:
                continue
            
            domain = row.get('Domain', '').strip().lower()
            link = row.get('Link', '').strip()
            anchor = row.get('Anchor', '')
            rank = row.get('Rank', '0')
            
            # Filtrar comparadores
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue
            
            # Filtrar duplicados
            if link in seen_urls:
                continue
            seen_urls.add(link)
            
            # Extraer precio
            current_price, original_price, is_offer = parse_price_from_text(anchor)
            
            # Limpiar título
            title = clean_product_title(anchor)
            if title:
                title = title.strip()
            
            if not title or len(title) < 5:
                continue
            
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
            )
            
            products.append(product)
            
        except Exception as e:
            errors += 1
            logger.warning(f"Error en fila {row_num}: {e}")
            continue
    
    if errors > 0:
        logger.info(f"Parseado completado con {errors} errores en {len(products) + errors} filas")
    
    # Ordenar: primero los que tienen precio, luego por precio
    products.sort(key=lambda p: (0 if p.has_price else 1, p.price if p.has_price else float('inf')))
    
    return products


def group_products_by_type(products: List[Product]) -> Dict[str, List[Product]]:
    """Agrupa productos por tipo de resultado."""
    groups = {}
    for p in products:
        if p.result_type not in groups:
            groups[p.result_type] = []
        groups[p.result_type].append(p)
    return groups


def get_price_distribution(products: List[Product], bins: int = 10) -> List[dict]:
    """
    Calcula distribución de precios para gráfico.
    
    Returns:
        Lista de dicts con 'range' y 'count'
    """
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
        count = len([p for p in prices if low <= p < high or (i == bins - 1 and p == high)])
        
        if count > 0:
            distribution.append({
                "range": f"{low:.0f}-{high:.0f}€",
                "count": count,
                "low": low,
                "high": high
            })
    
    return distribution
