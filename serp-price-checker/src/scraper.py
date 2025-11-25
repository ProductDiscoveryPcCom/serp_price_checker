import requests
from urllib.parse import urlparse, quote
from .models import SERPResult


# Ciudades españolas con sus códigos de ubicación para Google
SPANISH_CITIES = {
    "Madrid": "Madrid,Community of Madrid,Spain",
    "Barcelona": "Barcelona,Catalonia,Spain",
    "Valencia": "Valencia,Valencian Community,Spain",
    "Sevilla": "Seville,Andalusia,Spain",
    "Bilbao": "Bilbao,Basque Country,Spain",
    "Málaga": "Malaga,Andalusia,Spain",
}


def scrape_google_serp(
    query: str, 
    zenrows_api_key: str, 
    num_results: int = 20,
    location: str = "Madrid,Community of Madrid,Spain"
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
    
    params = {
        "apikey": zenrows_api_key,
        "gl": "es",           # País: España
        "hl": "es",           # Idioma: Español
        "cr": "countryES",    # Restringir a resultados de España
        "num": str(num_results),
        "location": location,  # Geolocalización
        "google_domain": "google.es",  # Dominio español
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
