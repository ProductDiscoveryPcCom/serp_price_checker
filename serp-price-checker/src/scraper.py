import requests
from urllib.parse import urlparse, quote_plus
from .models import SERPResult


def scrape_google_shopping(query: str, zenrows_api_key: str) -> str:
    """
    Obtiene el HTML de Google Shopping usando ZenRows Universal Scraper.
    
    Args:
        query: Término de búsqueda
        zenrows_api_key: API key de ZenRows
    
    Returns:
        HTML de la página de Google Shopping
    """
    # Construir URL de Google Shopping España
    google_shopping_url = (
        f"https://www.google.es/search?"
        f"q={quote_plus(query)}&tbm=shop&gl=es&hl=es"
    )
    
    # ZenRows Universal Scraper API
    zenrows_url = "https://api.zenrows.com/v1/"
    
    params = {
        "apikey": zenrows_api_key,
        "url": google_shopping_url,
        "js_render": "true",  # Google Shopping necesita JS
        "premium_proxy": "true",
        "proxy_country": "es",
    }
    
    response = requests.get(zenrows_url, params=params, timeout=90)
    response.raise_for_status()
    
    return response.text


def scrape_google_serp(query: str, zenrows_api_key: str, num_results: int = 10) -> list[SERPResult]:
    """
    Obtiene resultados orgánicos de Google.es usando ZenRows SERP API.
    Mantenemos esta función por si se quiere combinar con Shopping.
    """
    from urllib.parse import quote
    
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
    
    try:
        data = response.json()
    except Exception:
        raise ValueError(f"Respuesta no es JSON válido: {response.text[:200]}")
    
    return parse_serp_json(data)


def parse_serp_json(data: dict) -> list[SERPResult]:
    """Parsea la respuesta JSON de ZenRows SERP API."""
    results = []
    organic_results = data.get("organic_results", [])
    
    for position, item in enumerate(organic_results, 1):
        try:
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            domain = extract_domain(url)
            
            results.append(SERPResult(
                position=position,
                title=title,
                url=url,
                domain=domain,
                snippet=snippet,
                price=None,
                price_raw=None
            ))
        except Exception:
            continue
    
    return results


def extract_domain(url: str) -> str:
    """Extrae el dominio limpio de una URL."""
    if not url:
        return ""
    return urlparse(url).netloc.replace('www.', '')
