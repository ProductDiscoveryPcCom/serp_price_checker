import json
import re
from dataclasses import dataclass, field
from typing import Optional, List
import anthropic
import openai

from .models import ShoppingResult, PriceAnalysis


@dataclass
class ProductFeatures:
    """Características extraídas de un producto."""
    brand: str = ""
    model: str = ""
    processor: str = ""
    ram: str = ""
    storage: str = ""
    gpu: str = ""
    screen: str = ""
    os: str = ""
    extras: str = ""


def extract_features_with_claude(products: list[dict], api_key: str) -> list[dict]:
    """
    Usa Claude para extraer características detalladas de los productos.
    """
    if not products or not api_key:
        return products
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Preparar lista de títulos
    titles = [p.get('title', '') for p in products]
    
    prompt = f"""Analiza estos títulos de productos (portátiles/laptops) y extrae las características técnicas de cada uno.

TÍTULOS:
{json.dumps(titles, ensure_ascii=False, indent=2)}

Para cada producto, extrae:
- brand: Marca (MSI, ASUS, Acer, HP, Lenovo, etc.)
- model: Código de modelo (ej: B13WFKG-687XES)
- processor: Procesador completo (ej: Intel Core i7-13620H)
- ram: RAM (ej: 16GB DDR5)
- storage: Almacenamiento (ej: 1TB SSD)
- gpu: Tarjeta gráfica (ej: RTX 5060 8GB)
- screen: Pantalla (ej: 15.6" FHD 144Hz)
- os: Sistema operativo (Windows 11, FreeDOS, Sin SO)

Responde SOLO con un JSON array. Cada elemento debe tener los campos anteriores.
Si no encuentras un dato, usa cadena vacía "".

JSON:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        
        # Limpiar respuesta
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        features_list = json.loads(response_text.strip())
        
        # Combinar con productos originales
        for i, product in enumerate(products):
            if i < len(features_list):
                features = features_list[i]
                product['brand'] = features.get('brand', product.get('brand', ''))
                product['model'] = features.get('model', product.get('model', ''))
                product['processor'] = features.get('processor', product.get('processor', ''))
                product['ram'] = features.get('ram', product.get('ram', ''))
                product['storage'] = features.get('storage', product.get('storage', ''))
                product['gpu'] = features.get('gpu', product.get('gpu', ''))
                product['screen'] = features.get('screen', product.get('screen', ''))
                product['os'] = features.get('os', product.get('os', ''))
        
        return products
        
    except Exception as e:
        print(f"Error extrayendo características con Claude: {e}")
        return products


def extract_features_with_openai(products: list[dict], api_key: str) -> list[dict]:
    """
    Usa GPT para extraer características detalladas de los productos.
    """
    if not products or not api_key:
        return products
    
    client = openai.OpenAI(api_key=api_key)
    
    titles = [p.get('title', '') for p in products]
    
    prompt = f"""Analiza estos títulos de productos (portátiles/laptops) y extrae las características técnicas.

TÍTULOS:
{json.dumps(titles, ensure_ascii=False, indent=2)}

Para cada producto extrae: brand, model, processor, ram, storage, gpu, screen, os.
Responde SOLO con un JSON array. Si no encuentras un dato, usa "".

JSON:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        data = json.loads(response_text)
        
        # Puede venir como {"products": [...]} o directamente [...]
        features_list = data if isinstance(data, list) else data.get('products', data.get('items', []))
        
        for i, product in enumerate(products):
            if i < len(features_list):
                features = features_list[i]
                product['brand'] = features.get('brand', product.get('brand', ''))
                product['model'] = features.get('model', product.get('model', ''))
                product['processor'] = features.get('processor', product.get('processor', ''))
                product['ram'] = features.get('ram', product.get('ram', ''))
                product['storage'] = features.get('storage', product.get('storage', ''))
                product['gpu'] = features.get('gpu', product.get('gpu', ''))
                product['screen'] = features.get('screen', product.get('screen', ''))
                product['os'] = features.get('os', product.get('os', ''))
        
        return products
        
    except Exception as e:
        print(f"Error extrayendo características con GPT: {e}")
        return products


def extract_prices_with_claude(query: str, serp_data: dict, api_key: str) -> list:
    """Extrae precios de SERP data usando Claude."""
    from .models import ShoppingResult
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Analiza estos resultados de búsqueda de Google para "{query}" y extrae los productos con precios.

DATOS SERP:
{json.dumps(serp_data, ensure_ascii=False)[:8000]}

Para cada producto encontrado, extrae:
- title: Nombre del producto
- price: Precio en euros (número decimal)
- store: Nombre de la tienda
- url: URL del producto

Responde SOLO con JSON array. Ejemplo:
[{{"title": "Producto X", "price": 599.99, "store": "Amazon", "url": "https://..."}}]

JSON:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        items = json.loads(text.strip())
        
        results = []
        for i, item in enumerate(items, 1):
            price = item.get('price', 0)
            if isinstance(price, str):
                price = float(re.sub(r'[^\d.]', '', price) or 0)
            
            if price > 0:
                results.append(ShoppingResult(
                    position=i,
                    title=item.get('title', ''),
                    price=price,
                    store=item.get('store', ''),
                    url=item.get('url', '')
                ))
        
        return results
        
    except Exception as e:
        print(f"Error con Claude: {e}")
        return []


def extract_prices_with_openai(query: str, serp_data: dict, api_key: str) -> list:
    """Extrae precios de SERP data usando GPT."""
    from .models import ShoppingResult
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""Analiza resultados de búsqueda para "{query}" y extrae productos con precios.

DATOS:
{json.dumps(serp_data, ensure_ascii=False)[:8000]}

Extrae: title, price (número), store, url.
Responde con JSON array.

JSON:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        items = data if isinstance(data, list) else data.get('products', data.get('items', []))
        
        results = []
        for i, item in enumerate(items, 1):
            price = item.get('price', 0)
            if isinstance(price, str):
                price = float(re.sub(r'[^\d.]', '', price) or 0)
            
            if price > 0:
                results.append(ShoppingResult(
                    position=i,
                    title=item.get('title', ''),
                    price=price,
                    store=item.get('store', ''),
                    url=item.get('url', '')
                ))
        
        return results
        
    except Exception as e:
        print(f"Error con GPT: {e}")
        return []


def agent_scrape_and_extract(
    urls: list[str],
    zenrows_api_key: str,
    llm_provider: str,
    llm_api_key: str,
    openai_api_key: str = None
) -> list[dict]:
    """
    Agente que scrapea URLs y extrae información de productos usando LLM.
    
    Args:
        urls: Lista de URLs a scrapear
        zenrows_api_key: API key de ZenRows
        llm_provider: "claude", "openai" o "mixto"
        llm_api_key: API key del LLM principal
        openai_api_key: API key de OpenAI (para mixto)
    
    Returns:
        Lista de productos con información extraída
    """
    import requests
    
    results = []
    
    for url in urls[:10]:  # Limitar a 10 URLs para no abusar
        try:
            # Scrapear con ZenRows
            params = {
                "url": url,
                "apikey": zenrows_api_key,
                "js_render": "true",
                "premium_proxy": "true",
                "proxy_country": "es",
            }
            
            response = requests.get(
                "https://api.zenrows.com/v1/",
                params=params,
                timeout=30
            )
            
            if response.status_code != 200:
                continue
            
            html = response.text[:10000]  # Limitar tamaño
            
            # Extraer info con LLM
            if "claude" in llm_provider.lower():
                product_info = _extract_from_html_claude(html, url, llm_api_key)
            else:
                product_info = _extract_from_html_openai(html, url, openai_api_key or llm_api_key)
            
            if product_info:
                results.append(product_info)
                
        except Exception as e:
            print(f"Error scrapeando {url}: {e}")
            continue
    
    return results


def _extract_from_html_claude(html: str, url: str, api_key: str) -> dict:
    """Extrae información de producto del HTML usando Claude."""
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Extrae la información del producto de este HTML de una página de e-commerce.

URL: {url}
HTML (fragmento):
{html[:5000]}

Extrae:
- title: Nombre completo del producto
- price: Precio actual en euros (número)
- original_price: Precio original si hay descuento (número o null)
- brand, model, processor, ram, storage, gpu, screen, os

Responde SOLO con JSON objeto.

JSON:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        data = json.loads(text.strip())
        data['url'] = url
        return data
        
    except:
        return None


def _extract_from_html_openai(html: str, url: str, api_key: str) -> dict:
    """Extrae información de producto del HTML usando GPT."""
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""Extrae info del producto de este HTML.

URL: {url}
HTML:
{html[:5000]}

Extrae: title, price (número), original_price, brand, model, processor, ram, storage, gpu, screen, os
Responde con JSON objeto.

JSON:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        data['url'] = url
        return data
        
    except:
        return None


def build_analysis(
    query: str,
    your_domain: str,
    your_price: float,
    shopping_results: list
) -> PriceAnalysis:
    """
    Construye el análisis de precios.
    """
    your_domain_clean = your_domain.lower().replace('www.', '')
    
    # Filtrar solo productos con precio
    products_with_price = [
        r for r in shopping_results 
        if hasattr(r, 'price') and r.price and r.price > 0
    ]
    
    # Encontrar tu posición en SERP (cualquier producto)
    your_serp_position = None
    for i, result in enumerate(shopping_results, 1):
        store = getattr(result, 'store', '').lower() if hasattr(result, 'store') else ''
        url = getattr(result, 'url', '').lower() if hasattr(result, 'url') else ''
        if your_domain_clean in store or your_domain_clean in url:
            your_serp_position = i
            break
    
    # Ordenar por precio (solo los que tienen precio)
    sorted_by_price = sorted(products_with_price, key=lambda x: x.price)
    
    # Calcular tu posición en ranking de precios
    your_price_position = 1
    for r in sorted_by_price:
        if r.price < your_price:
            your_price_position += 1
        else:
            break
    
    # Encontrar más barato y más caro
    cheapest = sorted_by_price[0] if sorted_by_price else None
    most_expensive = sorted_by_price[-1] if sorted_by_price else None
    
    # Calcular media
    avg_price = None
    if sorted_by_price:
        avg_price = sum(r.price for r in sorted_by_price) / len(sorted_by_price)
    
    return PriceAnalysis(
        query=query,
        your_domain=your_domain,
        your_price=your_price,
        your_serp_position=your_serp_position,
        your_price_position=your_price_position,
        total_competitors=len(sorted_by_price),
        cheapest_competitor=cheapest,
        most_expensive_competitor=most_expensive,
        average_price=avg_price,
        all_results=shopping_results
    )
