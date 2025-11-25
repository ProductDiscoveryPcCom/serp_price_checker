import json
import re
import anthropic
import openai
from .models import ShoppingResult, CompetitorAnalysis


def preprocess_html(html: str) -> dict:
    """
    Preprocesa el HTML para detectar si contiene precios y extraer patrones útiles.
    Retorna estadísticas sobre el contenido.
    """
    stats = {
        "length": len(html),
        "has_euro_symbol": "€" in html,
        "has_eur_text": "EUR" in html.upper(),
        "price_patterns_found": [],
        "potential_stores": [],
    }
    
    # Buscar patrones de precio españoles
    price_patterns = [
        r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€',  # 1.299,00 €
        r'€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # € 1.299,00
        r'(\d+(?:,\d{2})?)\s*€',  # 449,99 €
        r'data-price["\']?\s*[:=]\s*["\']?(\d+(?:[.,]\d+)?)',  # data-price="449.99"
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, html)
        if matches:
            stats["price_patterns_found"].extend(matches[:10])  # Limitar a 10
    
    # Buscar tiendas conocidas
    known_stores = [
        "amazon", "mediamarkt", "pccomponentes", "fnac", "elcorteingles",
        "worten", "carrefour", "aliexpress", "ebay", "apple.com"
    ]
    for store in known_stores:
        if store.lower() in html.lower():
            stats["potential_stores"].append(store)
    
    return stats


SHOPPING_EXTRACTION_PROMPT = """Eres un experto en extracción de datos de HTML. Analiza el siguiente HTML de una página de resultados de Google Shopping España.

PRODUCTO BUSCADO: {query}

HTML:
{html}

TAREA: Extrae TODOS los productos con sus precios del HTML.

PISTAS PARA ENCONTRAR PRODUCTOS:
- Los precios en España usan formato: "449,00 €", "1.299 €", "€449", etc.
- Busca patrones como: data-price, aria-label con precios, spans/divs con €
- Los nombres de tienda suelen estar cerca de los precios
- Las URLs de producto contienen dominios como amazon.es, pccomponentes.com, mediamarkt.es, etc.

EXTRAE:
- title: nombre completo del producto
- price: precio como número decimal (ej: 449.00, no "449 €")
- store: nombre de la tienda (Amazon, MediaMarkt, PcComponentes, etc.)
- url: URL del producto si la encuentras

IMPORTANTE:
- Convierte precios españoles: "1.299,00 €" → 1299.00
- Si ves "Desde X €", usa X como precio
- Incluye TODOS los productos que encuentres, aunque sean variantes

Responde ÚNICAMENTE con este JSON (sin explicaciones, sin markdown):
{{"products": [{{"title": "...", "price": 123.45, "store": "...", "url": "..."}}], "total_found": N}}

Si el HTML no contiene productos o precios visibles, responde: {{"products": [], "total_found": 0, "reason": "descripción breve del problema"}}"""


def extract_shopping_with_claude(
    query: str,
    html: str,
    api_key: str
) -> list[ShoppingResult]:
    """Extrae productos de Google Shopping usando Claude."""
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Limitar HTML para no exceder contexto (aprox 100k chars)
    html_truncated = html[:150000] if len(html) > 150000 else html
    
    prompt = SHOPPING_EXTRACTION_PROMPT.format(
        query=query,
        html=html_truncated
    )
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Limpiar posible markdown
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Encontrar inicio y fin del JSON
            start_idx = 1 if lines[0].startswith("```") else 0
            end_idx = len(lines) - 1 if lines[-1] == "```" else len(lines)
            response_text = "\n".join(lines[start_idx:end_idx])
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()
        
        data = json.loads(response_text)
        
        products = []
        for i, item in enumerate(data.get("products", []), 1):
            try:
                price = item.get("price")
                if isinstance(price, str):
                    # Limpiar precio si viene como string
                    price = price.replace("€", "").replace(",", ".").strip()
                    price = float(price)
                
                products.append(ShoppingResult(
                    position=i,
                    title=item.get("title", ""),
                    price=float(price) if price else None,
                    store=item.get("store", ""),
                    url=item.get("url")
                ))
            except (ValueError, TypeError):
                continue
        
        return products
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parseando respuesta JSON de Claude: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error en extracción con Claude: {str(e)}")


def extract_shopping_with_openai(
    query: str,
    html: str,
    api_key: str
) -> list[ShoppingResult]:
    """Extrae productos de Google Shopping usando OpenAI GPT."""
    
    client = openai.OpenAI(api_key=api_key)
    
    # Limitar HTML
    html_truncated = html[:100000] if len(html) > 100000 else html
    
    prompt = SHOPPING_EXTRACTION_PROMPT.format(
        query=query,
        html=html_truncated
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        products = []
        for i, item in enumerate(data.get("products", []), 1):
            try:
                price = item.get("price")
                if isinstance(price, str):
                    price = price.replace("€", "").replace(",", ".").strip()
                    price = float(price)
                
                products.append(ShoppingResult(
                    position=i,
                    title=item.get("title", ""),
                    price=float(price) if price else None,
                    store=item.get("store", ""),
                    url=item.get("url")
                ))
            except (ValueError, TypeError):
                continue
        
        return products
        
    except Exception as e:
        raise ValueError(f"Error en extracción con OpenAI: {str(e)}")


def build_analysis(
    query: str,
    your_domain: str,
    your_price: float,
    shopping_results: list[ShoppingResult]
) -> CompetitorAnalysis:
    """
    Construye el análisis final con posiciones y ranking.
    """
    # Filtrar productos con precio válido
    valid_products = [p for p in shopping_results if p.price is not None and p.price > 0]
    
    # Ordenar por precio
    valid_products.sort(key=lambda x: x.price)
    
    # Buscar si tu tienda aparece
    your_domain_clean = your_domain.replace('www.', '').lower()
    your_shopping_position = None
    
    for product in valid_products:
        store_clean = product.store.lower() if product.store else ""
        if your_domain_clean in store_clean or store_clean in your_domain_clean:
            your_shopping_position = product.position
            break
    
    # Calcular tu posición por precio
    your_price_position = 1
    for product in valid_products:
        if product.price and product.price < your_price:
            your_price_position += 1
    
    return CompetitorAnalysis(
        query=query,
        your_domain=your_domain,
        your_price=your_price,
        competitors=valid_products,
        your_serp_position=your_shopping_position,  # Ahora es posición en Shopping
        your_price_position=your_price_position,
        total_organic_results=len(shopping_results)
    )


# Mantener compatibilidad con imports anteriores
def analyze_with_claude(query, serp_results, api_key):
    """Deprecated: usar extract_shopping_with_claude"""
    pass

def analyze_with_openai(query, serp_results, api_key):
    """Deprecated: usar extract_shopping_with_openai"""
    pass
