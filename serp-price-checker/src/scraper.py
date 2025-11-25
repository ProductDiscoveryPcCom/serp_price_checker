import requests
from urllib.parse import urlparse, quote
from .models import SERPResult


def scrape_google_serp(query: str, zenrows_api_key: str, num_results: int = 20) -> dict:
    """
    Obtiene resultados de Google.es usando ZenRows SERP API.
    Devuelve el JSON completo para que Claude lo analice.
    
    Args:
        query: Término de búsqueda
        zenrows_api_key: API key de ZenRows
        num_results: Número de resultados
    
    Returns:
        Dict con la respuesta JSON completa de ZenRows
    """
    encoded_query = quote(query)
    api_endpoint = f"https://serp.api.zenrows.com/v1/targets/google/search/{encoded_query}"
    
    params = {
        "apikey": zenrows_api_key,
        "gl": "es",
        "hl": "es",
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
