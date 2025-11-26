import json
import anthropic
import openai
from .models import ShoppingResult, CompetitorAnalysis


PRICE_EXTRACTION_PROMPT = """Eres un experto en análisis de resultados de búsqueda de Google España para productos de electrónica.

PRODUCTO BUSCADO: {query}

RESULTADOS DE GOOGLE ESPAÑA (JSON):
{serp_json}

TAREA: Analiza estos resultados de búsqueda y extrae información de precios de productos de TIENDAS ESPAÑOLAS.

INSTRUCCIONES:
1. Busca precios en los títulos y snippets (ej: "449 €", "desde 1.299€", "PVP: 899,00€")
2. Identifica la tienda de cada resultado por el dominio o título
3. SOLO incluye resultados de tiendas que vendan en España (dominios .es o tiendas conocidas en España)
4. Convierte precios españoles a número: "1.299,00 €" → 1299.00
5. IGNORA resultados en inglés o de tiendas no españolas

TIENDAS ESPAÑOLAS A BUSCAR (priorizar estas):
- amazon.es, pccomponentes.com, mediamarkt.es, fnac.es, elcorteingles.es
- worten.es, carrefour.es, apple.com/es, backmarket.es, phonehouse.es
- coolmod.com, versus-gamers.com, ldlc.com, tuimeilibre.com
- También cualquier otra tienda online española (.es)

NO INCLUIR:
- Páginas de comparadores (idealo, google shopping, kelkoo)
- Páginas de noticias o reviews
- Tiendas de otros países (amazon.com, amazon.de, etc.)

Responde SOLO con este JSON (sin markdown, sin explicaciones):
{{
    "products": [
        {{
            "title": "nombre del producto tal como aparece",
            "price": 899.99,
            "store": "nombre de la tienda",
            "url": "url del resultado",
            "source": "organic o ad"
        }}
    ],
    "total_found": número
}}

Si no encuentras productos con precios de tiendas españolas, responde: {{"products": [], "total_found": 0}}"""


def extract_prices_with_claude(
    query: str,
    serp_data: dict,
    api_key: str
) -> list[ShoppingResult]:
    """Extrae productos y precios de resultados SERP usando Claude."""
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Simplificar JSON para el prompt (solo lo relevante)
    simplified_data = {
        "organic_results": serp_data.get("organic_results", [])[:15],
        "ad_results": serp_data.get("ad_results", [])[:5],
    }
    
    prompt = PRICE_EXTRACTION_PROMPT.format(
        query=query,
        serp_json=json.dumps(simplified_data, indent=2, ensure_ascii=False)
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
            start_idx = 1
            end_idx = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            response_text = "\n".join(lines[start_idx:end_idx])
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()
        
        data = json.loads(response_text)
        
        products = []
        for i, item in enumerate(data.get("products", []), 1):
            try:
                price = item.get("price")
                if isinstance(price, str):
                    price = price.replace("€", "").replace(",", ".").replace(" ", "").strip()
                    price = float(price)
                
                if price and price > 0:
                    products.append(ShoppingResult(
                        position=i,
                        title=item.get("title", ""),
                        price=float(price),
                        store=item.get("store", ""),
                        url=item.get("url")
                    ))
            except (ValueError, TypeError):
                continue
        
        return products
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parseando JSON de Claude: {str(e)}\nRespuesta: {response_text[:500]}")
    except Exception as e:
        raise ValueError(f"Error en extracción con Claude: {str(e)}")


def extract_prices_with_openai(
    query: str,
    serp_data: dict,
    api_key: str
) -> list[ShoppingResult]:
    """Extrae productos y precios de resultados SERP usando OpenAI GPT."""
    
    client = openai.OpenAI(api_key=api_key)
    
    simplified_data = {
        "organic_results": serp_data.get("organic_results", [])[:15],
        "ad_results": serp_data.get("ad_results", [])[:5],
    }
    
    prompt = PRICE_EXTRACTION_PROMPT.format(
        query=query,
        serp_json=json.dumps(simplified_data, indent=2, ensure_ascii=False)
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
                    price = price.replace("€", "").replace(",", ".").replace(" ", "").strip()
                    price = float(price)
                
                if price and price > 0:
                    products.append(ShoppingResult(
                        position=i,
                        title=item.get("title", ""),
                        price=float(price),
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
    """Construye el análisis final con posiciones y ranking."""
    
    # Filtrar productos con precio válido
    valid_products = [p for p in shopping_results if p.price is not None and p.price > 0]
    
    # Ordenar por precio
    valid_products.sort(key=lambda x: x.price)
    
    # Buscar si tu tienda aparece
    your_domain_clean = your_domain.replace('www.', '').lower()
    your_position = None
    
    for i, product in enumerate(valid_products, 1):
        store_clean = product.store.lower() if product.store else ""
        url_clean = product.url.lower() if product.url else ""
        if your_domain_clean in store_clean or your_domain_clean in url_clean:
            your_position = i
            break
    
    # Calcular tu posición por precio
    your_price_position = 1
    for product in valid_products:
        if product.price < your_price:
            your_price_position += 1
    
    return CompetitorAnalysis(
        query=query,
        your_domain=your_domain,
        your_price=your_price,
        competitors=valid_products,
        your_serp_position=your_position,
        your_price_position=your_price_position,
        total_organic_results=len(shopping_results)
    )
