import requests
import re
import csv
import io
from urllib.parse import urlparse, quote
from .models import SERPResult


# Ciudades españolas con sus códigos de ubicación para Google
SPANISH_CITIES = {
    "Madrid": "Madrid,Spain",
    "Barcelona": "Barcelona,Spain",
    "Valencia": "Valencia,Spain",
    "Sevilla": "Seville,Spain",
    "Bilbao": "Bilbao,Spain",
    "Málaga": "Malaga,Spain",
}


def parse_extension_csv(csv_content: str) -> list[dict]:
    """
    Parsea el CSV exportado por la extensión 'Google Rank Checker'.
    Extrae Shopping Ads y resultados orgánicos con precios.
    
    Args:
        csv_content: Contenido del CSV como string
        
    Returns:
        Lista de diccionarios con productos y precios
    """
    results = []
    
    # Leer CSV
    reader = csv.DictReader(io.StringIO(csv_content), delimiter='\t')
    
    # Detectar si es separado por tabs o comas
    first_line = csv_content.split('\n')[0]
    if '\t' in first_line:
        reader = csv.DictReader(io.StringIO(csv_content), delimiter='\t')
    else:
        reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in reader:
        try:
            # Obtener campos del CSV
            result_type = row.get('Type', '')
            domain = row.get('Domain', '')
            link = row.get('Link', '')
            anchor = row.get('Anchor', '')
            rank = row.get('Rank', '0')
            
            # Solo procesar Shopping Ads y Organic con contenido
            if not anchor or not domain:
                continue
                
            # Filtrar tipos relevantes (Shopping Ads principalmente)
            if 'Shopping' not in result_type and 'Organic' not in result_type:
                continue
            
            # Filtrar comparadores y agregadores
            skip_domains = ['kelkoo', 'idealo', 'shopping.com', 'shoparize', 
                          'producthero', 'delupe', 'adference', 'klarna']
            if any(skip in domain.lower() for skip in skip_domains):
                continue
            
            # Extraer precio del anchor (formato: "Producto12345 €Tienda...")
            price = extract_price_from_anchor(anchor)
            
            if price:
                # Limpiar título (quitar precio y tienda del anchor)
                title = clean_title_from_anchor(anchor)
                
                results.append({
                    'title': title,
                    'price': price,
                    'store': domain.replace('www.', ''),
                    'url': link,
                    'type': result_type,
                    'rank': int(rank) if rank.isdigit() else 0
                })
                
        except Exception as e:
            continue
    
    # Ordenar por precio
    results.sort(key=lambda x: x['price'])
    
    # Eliminar duplicados por tienda (quedarse con el más barato)
    seen_stores = set()
    unique_results = []
    for r in results:
        store_key = r['store'].lower()
        if store_key not in seen_stores:
            seen_stores.add(store_key)
            unique_results.append(r)
    
    return unique_results


def extract_price_from_anchor(anchor: str) -> float | None:
    """
    Extrae el precio de un anchor de la extensión.
    Formatos: "48812 €", "598,50€", "1.299,00 €"
    """
    if not anchor:
        return None
    
    # Patrones de precio español
    patterns = [
        # Formato sin separadores: "48812 €" o "48812€" (céntimos incluidos sin separador)
        r'(\d{3,6})\s*€',
        # Formato con coma decimal: "598,50 €" o "1.299,00€"
        r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€',
        # Formato con punto decimal (inglés): "598.50€"
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*€',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, anchor)
        if match:
            price_str = match.group(1)
            return parse_spanish_price(price_str)
    
    return None


def parse_spanish_price(price_str: str) -> float | None:
    """
    Convierte un string de precio español a float.
    "1.299,00" → 1299.00
    "48812" → 488.12 (si tiene 5 dígitos, los 2 últimos son céntimos)
    """
    try:
        # Limpiar espacios
        price_str = price_str.strip()
        
        # Si tiene coma, es formato español normal
        if ',' in price_str:
            # Quitar puntos de miles, reemplazar coma por punto
            price_str = price_str.replace('.', '').replace(',', '.')
            return float(price_str)
        
        # Si solo tiene punto y parece decimal (ej: 598.50)
        if '.' in price_str and len(price_str.split('.')[-1]) == 2:
            return float(price_str.replace(',', ''))
        
        # Si es número sin separadores (ej: 48812 = 488,12€)
        if price_str.isdigit():
            num = int(price_str)
            # Si tiene 5+ dígitos, los últimos 2 son céntimos
            if num >= 10000:
                return num / 100
            # Si es menor, probablemente ya son euros enteros
            return float(num)
        
        # Quitar puntos de miles si los hay
        price_str = price_str.replace('.', '')
        return float(price_str)
        
    except:
        return None


def clean_title_from_anchor(anchor: str) -> str:
    """
    Limpia el título quitando precio, tienda y texto extra del anchor.
    """
    if not anchor:
        return ""
    
    # Quitar precio y todo lo que viene después
    # El precio suele ser el primer número grande seguido de €
    match = re.search(r'^(.+?)(\d{3,})\s*€', anchor)
    if match:
        return match.group(1).strip()
    
    # Si no hay precio, devolver primeros 100 chars
    return anchor[:100] if len(anchor) > 100 else anchor


def scrape_google_serp(
    query: str, 
    zenrows_api_key: str, 
    num_results: int = 20,
    location: str = "Madrid,Spain"
) -> dict:
    """
    Obtiene resultados de Google.es usando ZenRows SERP API.
    Configurado para España en español.
    
    Args:
        query: Término de búsqueda
        zenrows_api_key: API key de ZenRows
        num_results: Número de resultados
        location: Ubicación para geolocalización (ciudad española)
    
    Returns:
        Dict con la respuesta JSON completa de ZenRows
    """
    encoded_query = quote(query)
    api_endpoint = f"https://serp.api.zenrows.com/v1/targets/google/search/{encoded_query}"
    
    # Parámetros correctos para ZenRows SERP API
    params = {
        "apikey": zenrows_api_key,
        "tld": "es",              # TLD: google.es
        "country": "es",          # País: España  
        "location": location,     # Ubicación específica
        "num": str(num_results),
    }
    
    response = requests.get(api_endpoint, params=params, timeout=60)
    response.raise_for_status()
    
    return response.json()


def parse_serp_to_results(data: dict) -> list[SERPResult]:
    """
    Convierte la respuesta de ZenRows SERP API a lista de SERPResult.
    """
    results = []
    
    # Procesar resultados orgánicos
    organic_results = data.get("organic_results", [])
    for position, item in enumerate(organic_results, 1):
        results.append(SERPResult(
            position=position,
            title=item.get("title", ""),
            url=item.get("link", ""),
            domain=extract_domain(item.get("link", "")),
            snippet=item.get("snippet", ""),
            price=None,
            price_raw=None
        ))
    
    # Procesar anuncios (ad_results) - también pueden tener precios
    ad_results = data.get("ad_results", [])
    for item in ad_results:
        results.append(SERPResult(
            position=0,  # Los ads no tienen posición orgánica
            title=item.get("title", ""),
            url=item.get("link", ""),
            domain=extract_domain(item.get("displayed_link", "")),
            snippet=item.get("snippet", ""),
            price=None,
            price_raw=None
        ))
    
    return results


def extract_domain(url: str) -> str:
    """Extrae el dominio limpio de una URL."""
    if not url:
        return ""
    try:
        return urlparse(url).netloc.replace('www.', '')
    except:
        return ""
