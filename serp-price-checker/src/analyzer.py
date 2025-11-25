import json
import anthropic
import openai
from .models import ShoppingResult, CompetitorAnalysis


SHOPPING_EXTRACTION_PROMPT = """Analiza el siguiente HTML de Google Shopping y extrae los productos listados.

PRODUCTO BUSCADO: {query}

HTML DE GOOGLE SHOPPING:
```html
{html}
```

INSTRUCCIONES:
1. Extrae TODOS los productos que aparecen en los resultados de Shopping
2. Para cada producto extrae: título, precio (en euros), tienda/vendedor, y URL si está disponible
3. Solo incluye productos que coincidan con la búsqueda (mismo producto o muy similar)
4. El precio debe ser un número (ej: 899.99), sin símbolos de moneda
5. Si un producto tiene varios precios, usa el precio principal/más bajo

Responde SOLO con un JSON válido (sin markdown ni texto adicional):
{{
    "products": [
        {{
            "title": "nombre del producto",
            "price": 899.99,
            "store": "nombre de la tienda",
            "url": "url del producto o null"
        }}
    ],
    "total_found": número total de productos encontrados
}}

Si no encuentras productos, devuelve: {{"products": [], "total_found": 0}}"""


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
