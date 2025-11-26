import requests
import re
import csv
import io
from urllib.parse import urlparse, quote
from dataclasses import dataclass, field
from typing import Optional, List


# Ciudades españolas
SPANISH_CITIES = {
    "Madrid": "Madrid,Spain",
    "Barcelona": "Barcelona,Spain",
    "Valencia": "Valencia,Spain",
    "Sevilla": "Seville,Spain",
    "Bilbao": "Bilbao,Spain",
    "Málaga": "Malaga,Spain",
}

# Tipos válidos de la extensión
VALID_TYPES = ['Shopping Ads', 'Organic', 'Ads', 'Ads Sub']

# Dominios a filtrar (comparadores, CSS partners)
SKIP_DOMAINS = [
    'kelkoo', 'idealo', 'shopping.com', 'shoparize', 
    'producthero', 'delupe', 'adference', 'klarna',
    'redbrain', 'surferseo', 'google.com', 'docs.surferseo'
]


def is_valid_type(csv_type: str) -> bool:
    """Determina si el tipo es válido (no es un selector CSS)."""
    # Los tipos válidos son los que están en la lista
    return csv_type in VALID_TYPES


def extract_prices_from_anchor(anchor: str) -> tuple[float, Optional[float], bool]:
    """
    Extrae precios del anchor. Maneja ofertas con precio tachado.
    
    Formatos del CSV:
    - "Producto94900 €TiendaSin coste" = 949.00€ (5 dígitos = céntimos)
    - "OfertaProducto47900 €599 €TiendaSin coste" = oferta: ahora 479€, antes 599€
    - "Producto66900 €MediaMarkt ESSin coste" = 669.00€
    
    Regla: 5+ dígitos = céntimos, 3 dígitos = euros enteros
    
    Returns:
        (precio_actual, precio_original, es_oferta)
    """
    if not anchor:
        return (0.0, None, False)
    
    is_offer = 'Oferta' in anchor or 'oferta' in anchor
    
    # Buscar todos los precios: números de 3-6 dígitos seguidos de €
    price_pattern = r'(\d{3,6})\s*€'
    matches = re.findall(price_pattern, anchor)
    
    if not matches:
        return (0.0, None, False)
    
    # Convertir a floats según número de dígitos
    prices = []
    for match in matches:
        num = int(match)
        # 5 o 6 dígitos = céntimos (94900 = 949.00€)
        # 3 o 4 dígitos = euros enteros (599 = 599.00€, 1299 = 1299.00€)
        if len(match) >= 5:
            price = num / 100
        else:
            price = float(num)
        prices.append(price)
    
    if len(prices) == 1:
        return (prices[0], None, is_offer)
    elif len(prices) >= 2:
        # En ofertas: primer precio = actual, segundo = original (tachado)
        current = prices[0]
        original = prices[1] if prices[1] != current else None
        return (current, original, is_offer or original is not None)
    
    return (0.0, None, False)


def clean_title(anchor: str) -> str:
    """Extrae el título limpio del anchor."""
    if not anchor:
        return ""
    
    # Quitar "Oferta" al inicio
    title = re.sub(r'^Oferta\s*', '', anchor)
    
    # Quitar "Portátil " duplicado al inicio
    title = re.sub(r'^Portátil\s+Portátil\s+', 'Portátil ', title)
    
    # Buscar donde empieza el precio y cortar ahí
    price_match = re.search(r'\d{3,6}\s*€', title)
    if price_match:
        title = title[:price_match.start()]
    
    return title.strip()


def extract_product_features_regex(title: str) -> dict:
    """Extrae características del producto usando regex (fallback sin LLM)."""
    features = {
        'processor': '',
        'ram': '',
        'storage': '',
        'gpu': '',
        'screen': '',
        'os': '',
        'model': '',
        'brand': ''
    }
    
    title_lower = title.lower()
    
    # Marca
    brands = ['msi', 'asus', 'acer', 'lenovo', 'hp', 'dell', 'gigabyte', 'razer', 'alienware']
    for brand in brands:
        if brand in title_lower:
            features['brand'] = brand.upper()
            break
    
    # Procesador Intel (varias nomenclaturas)
    intel_patterns = [
        r'intel\s+core\s+(i\d+-\d+[a-z]*)',
        r'intel\s+core\s+(\d+[\s-]\d+[a-z]*)',  # Core 7 240H
        r'(i\d+-\d+[a-z]+)',
    ]
    for pattern in intel_patterns:
        match = re.search(pattern, title_lower)
        if match:
            features['processor'] = f"Intel Core {match.group(1).upper()}"
            break
    
    # AMD Ryzen
    if not features['processor']:
        amd_match = re.search(r'(amd\s+)?ryzen\s+(\d+[\s-]\d+[a-z]*)', title_lower)
        if amd_match:
            features['processor'] = f"AMD Ryzen {amd_match.group(2).upper()}"
    
    # RAM
    ram_match = re.search(r'(\d+)\s*gb\s*(ram|ddr)', title_lower)
    if ram_match:
        features['ram'] = f"{ram_match.group(1)}GB"
    else:
        # Buscar patrón como "16GB" o "32 GB" no seguido de SSD
        ram_match2 = re.search(r'(\d{1,2})\s*gb(?!\s*ssd)', title_lower)
        if ram_match2:
            gb = int(ram_match2.group(1))
            if gb in [8, 16, 32, 64]:  # Valores típicos de RAM
                features['ram'] = f"{gb}GB"
    
    # Almacenamiento
    storage_match = re.search(r'(\d+)\s*(tb|gb)\s*ssd', title_lower)
    if storage_match:
        features['storage'] = f"{storage_match.group(1)}{storage_match.group(2).upper()} SSD"
    
    # GPU NVIDIA
    gpu_patterns = [
        r'(rtx\s*\d{4})',
        r'(gtx\s*\d{4})',
        r'geforce\s+(rtx\s*\d{4})',
        r'geforce\s+(gtx\s*\d{4})',
    ]
    for pattern in gpu_patterns:
        gpu_match = re.search(pattern, title_lower)
        if gpu_match:
            features['gpu'] = gpu_match.group(1).upper().replace(' ', ' ')
            break
    
    # GPU AMD
    if not features['gpu']:
        radeon_match = re.search(r'radeon\s+(rx\s*\d{4})', title_lower)
        if radeon_match:
            features['gpu'] = f"Radeon {radeon_match.group(1).upper()}"
    
    # Pantalla
    screen_match = re.search(r'(\d{2}[.,]?\d?)["\']?\s*(full\s*hd|fhd|wuxga|qhd|4k|uhd)?', title_lower)
    if screen_match:
        size = screen_match.group(1).replace(',', '.')
        if not size.endswith('.'):
            if len(size) == 2:
                size = size  # Ya es correcto (15, 16, 17)
        features['screen'] = f'{size}"'
    
    # Sistema Operativo
    if 'windows 11' in title_lower:
        features['os'] = 'Windows 11'
    elif 'windows 10' in title_lower:
        features['os'] = 'Windows 10'
    elif 'freedos' in title_lower or 'free dos' in title_lower:
        features['os'] = 'FreeDOS'
    elif 'sin sistema' in title_lower:
        features['os'] = 'Sin SO'
    
    # Modelo (código del producto)
    model_patterns = [
        r'([a-z]\d{2}[a-z]{2,}[-]\d{3,}[a-z]*)',  # B13WFKG-687XES
        r'(\d{2}[a-z]{2,}\d+-\d+[a-z]*)',  # 15FA2018NS
    ]
    for pattern in model_patterns:
        model_match = re.search(pattern, title_lower)
        if model_match:
            features['model'] = model_match.group(1).upper()
            break
    
    return features


def parse_extension_csv(csv_content: str, include_type: bool = True) -> list[dict]:
    """
    Parsea el CSV de la extensión Google Rank Checker.
    
    Args:
        csv_content: Contenido del CSV
        include_type: Si incluir el tipo de resultado
        
    Returns:
        Lista de productos con sus datos
    """
    results = []
    seen_urls = set()
    
    # El CSV usa comas como delimitador
    reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in reader:
        try:
            csv_type = row.get('Type', '').strip()
            domain = row.get('Domain', '').strip()
            link = row.get('Link', '').strip()
            anchor = row.get('Anchor', '').strip()
            rank = row.get('Rank', '0').strip()
            
            # Saltar si no hay datos esenciales
            if not anchor or not domain or not link:
                continue
            
            # Solo procesar tipos válidos (Shopping Ads, Organic, Ads, Ads Sub)
            if not is_valid_type(csv_type):
                continue
            
            # Saltar URLs duplicadas
            if link in seen_urls:
                continue
            seen_urls.add(link)
            
            # Saltar dominios de comparadores
            domain_lower = domain.lower()
            if any(skip in domain_lower for skip in SKIP_DOMAINS):
                continue
            
            # Extraer precios (puede ser 0 para Organic/Ads)
            current_price, original_price, is_offer = extract_prices_from_anchor(anchor)
            
            # Extraer título limpio
            title = clean_title(anchor)
            
            # Para Organic/Ads sin precio, usar el anchor como título
            if not title or len(title) < 5:
                # Limpiar el anchor de URLs y dominios
                title = anchor.split('https://')[0].split('http://')[0]
                title = re.sub(r'[A-Za-z]+\.[a-z]{2,3}(?:/|$).*', '', title)
                title = title.strip()
            
            if not title or len(title) < 5:
                continue
            
            # Extraer características con regex (solo si tiene precio - es un producto)
            if current_price > 0:
                features = extract_product_features_regex(title)
            else:
                features = {
                    'processor': '', 'ram': '', 'storage': '',
                    'gpu': '', 'screen': '', 'os': '',
                    'model': '', 'brand': ''
                }
            
            result = {
                'title': title,
                'price': current_price,
                'original_price': original_price,
                'is_offer': is_offer,
                'store': domain.replace('www.', ''),
                'url': link,
                'type': csv_type,
                'rank': int(rank) if rank.isdigit() else 0,
                **features
            }
            
            results.append(result)
            
        except Exception as e:
            continue
    
    # Ordenar: primero los que tienen precio, luego por precio
    results.sort(key=lambda x: (x['price'] == 0, x['price']))
    
    return results


def group_by_store(results: list[dict]) -> dict[str, list[dict]]:
    """Agrupa resultados por tienda."""
    stores = {}
    for r in results:
        store = r['store']
        if store not in stores:
            stores[store] = []
        stores[store].append(r)
    return stores


def scrape_google_serp(
    query: str, 
    zenrows_api_key: str, 
    num_results: int = 20,
    location: str = "Madrid,Spain"
) -> dict:
    """Obtiene resultados de Google.es usando ZenRows SERP API."""
    encoded_query = quote(query)
    api_endpoint = f"https://serp.api.zenrows.com/v1/targets/google/search/{encoded_query}"
    
    params = {
        "apikey": zenrows_api_key,
        "tld": "es",
        "country": "es",
        "location": location,
        "num": str(num_results),
    }
    
    response = requests.get(api_endpoint, params=params, timeout=60)
    response.raise_for_status()
    
    return response.json()


def scrape_product_url(url: str, zenrows_api_key: str) -> dict:
    """Scrapea una URL de producto para obtener más detalles."""
    params = {
        "url": url,
        "apikey": zenrows_api_key,
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": "es",
    }
    
    try:
        response = requests.get(
            "https://api.zenrows.com/v1/",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return {"html": response.text, "success": True}
    except Exception as e:
        return {"html": "", "success": False, "error": str(e)}


def extract_domain(url: str) -> str:
    """Extrae el dominio limpio de una URL."""
    if not url:
        return ""
    try:
        return urlparse(url).netloc.replace('www.', '')
    except:
        return ""
