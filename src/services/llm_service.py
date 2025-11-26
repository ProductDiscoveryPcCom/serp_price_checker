"""Servicio de LLM para extracción de entidades de productos."""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProductEntities:
    """Entidades extraídas de un producto."""
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    capacity: Optional[str] = None
    resolution: Optional[str] = None
    refresh_rate: Optional[str] = None
    panel_type: Optional[str] = None
    processor: Optional[str] = None
    memory: Optional[str] = None
    storage: Optional[str] = None
    graphics: Optional[str] = None
    connectivity: Optional[str] = None
    price_detected: Optional[float] = None
    price_confidence: str = "none"  # none, low, medium, high
    raw_attributes: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para mostrar en UI."""
        result = {}
        if self.brand:
            result["Marca"] = self.brand
        if self.model:
            result["Modelo"] = self.model
        if self.size:
            result["Tamaño"] = self.size
        if self.color:
            result["Color"] = self.color
        if self.capacity:
            result["Capacidad"] = self.capacity
        if self.resolution:
            result["Resolución"] = self.resolution
        if self.refresh_rate:
            result["Frecuencia"] = self.refresh_rate
        if self.panel_type:
            result["Panel"] = self.panel_type
        if self.processor:
            result["Procesador"] = self.processor
        if self.memory:
            result["Memoria"] = self.memory
        if self.storage:
            result["Almacenamiento"] = self.storage
        if self.graphics:
            result["Gráficos"] = self.graphics
        if self.connectivity:
            result["Conectividad"] = self.connectivity
        
        # Añadir atributos raw que no estén ya
        for key, value in self.raw_attributes.items():
            if key not in result:
                result[key] = value
        
        return result


def extract_entities_with_llm(
    title: str,
    current_price: Optional[float],
    api_key: str,
    provider: str = "anthropic"
) -> ProductEntities:
    """
    Extrae entidades del título usando LLM.
    
    Args:
        title: Título del producto
        current_price: Precio actualmente detectado (puede ser None o incorrecto)
        api_key: API key del proveedor
        provider: "anthropic" o "openai"
    
    Returns:
        ProductEntities con los atributos extraídos
    """
    if provider == "anthropic":
        return _extract_with_anthropic(title, current_price, api_key)
    elif provider == "openai":
        return _extract_with_openai(title, current_price, api_key)
    else:
        raise ValueError(f"Provider no soportado: {provider}")


def _extract_with_anthropic(title: str, current_price: Optional[float], api_key: str) -> ProductEntities:
    """Extrae entidades usando Claude."""
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = _build_extraction_prompt(title, current_price)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        return _parse_llm_response(response_text, title)
        
    except ImportError:
        logger.error("anthropic package not installed")
        return _fallback_extraction(title, current_price)
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {e}")
        return _fallback_extraction(title, current_price)


def _extract_with_openai(title: str, current_price: Optional[float], api_key: str) -> ProductEntities:
    """Extrae entidades usando OpenAI."""
    try:
        import openai
        
        client = openai.OpenAI(api_key=api_key)
        
        prompt = _build_extraction_prompt(title, current_price)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024
        )
        
        response_text = response.choices[0].message.content
        return _parse_llm_response(response_text, title)
        
    except ImportError:
        logger.error("openai package not installed")
        return _fallback_extraction(title, current_price)
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return _fallback_extraction(title, current_price)


def _build_extraction_prompt(title: str, current_price: Optional[float]) -> str:
    """Construye el prompt para extracción de entidades."""
    price_context = ""
    if current_price:
        price_context = f"\nPrecio detectado actualmente: {current_price:.2f}€ (verifica si es correcto)"
    else:
        price_context = "\nNo se ha detectado precio. Busca si hay algún precio en el título."
    
    return f"""Analiza este título de producto y extrae las entidades/atributos.

TÍTULO: {title}
{price_context}

Responde SOLO con un JSON válido con esta estructura:
{{
    "brand": "marca del producto o null",
    "model": "modelo/referencia o null",
    "size": "tamaño (ej: 27\", 15.6\", 256GB) o null",
    "color": "color o null",
    "capacity": "capacidad de almacenamiento o null",
    "resolution": "resolución (ej: FullHD, 4K, QHD) o null",
    "refresh_rate": "frecuencia de refresco (ej: 144Hz) o null",
    "panel_type": "tipo de panel (IPS, VA, OLED) o null",
    "processor": "procesador o null",
    "memory": "memoria RAM o null",
    "storage": "almacenamiento o null",
    "graphics": "tarjeta gráfica o null",
    "connectivity": "conectividad especial (WiFi 6, Bluetooth, etc) o null",
    "price_detected": número del precio detectado o null,
    "price_confidence": "high" si el precio es claro, "medium" si es probable, "low" si es dudoso, "none" si no hay precio,
    "other_attributes": {{}} diccionario con otros atributos relevantes encontrados
}}

IMPORTANTE:
- Extrae SOLO lo que esté explícitamente en el título
- No inventes ni asumas información
- El precio puede estar en formato: "599€", "599,99€", "59900" (céntimos)
- Responde SOLO el JSON, sin explicaciones"""


def _parse_llm_response(response: str, original_title: str) -> ProductEntities:
    """Parsea la respuesta del LLM."""
    try:
        # Limpiar respuesta
        response = response.strip()
        
        # Quitar markdown si existe
        if response.startswith("```"):
            response = re.sub(r'^```json?\n?', '', response)
            response = re.sub(r'\n?```$', '', response)
        
        data = json.loads(response)
        
        entities = ProductEntities(
            brand=data.get("brand"),
            model=data.get("model"),
            size=data.get("size"),
            color=data.get("color"),
            capacity=data.get("capacity"),
            resolution=data.get("resolution"),
            refresh_rate=data.get("refresh_rate"),
            panel_type=data.get("panel_type"),
            processor=data.get("processor"),
            memory=data.get("memory"),
            storage=data.get("storage"),
            graphics=data.get("graphics"),
            connectivity=data.get("connectivity"),
            price_detected=data.get("price_detected"),
            price_confidence=data.get("price_confidence", "none"),
            raw_attributes=data.get("other_attributes", {})
        )
        
        return entities
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return _fallback_extraction(original_title, None)


def _fallback_extraction(title: str, current_price: Optional[float]) -> ProductEntities:
    """Extracción básica sin LLM como fallback."""
    entities = ProductEntities()
    title_lower = title.lower()
    
    # Marcas conocidas
    brands = [
        'msi', 'asus', 'acer', 'lenovo', 'hp', 'dell', 'samsung', 'lg', 'sony',
        'apple', 'xiaomi', 'huawei', 'aoc', 'benq', 'viewsonic', 'philips',
        'gigabyte', 'corsair', 'razer', 'logitech', 'steelseries'
    ]
    for brand in brands:
        if brand in title_lower:
            entities.brand = brand.upper() if brand in ['msi', 'asus', 'hp', 'lg', 'aoc'] else brand.title()
            break
    
    # Tamaño de pantalla
    size_match = re.search(r'(\d{1,2}(?:[.,]\d)?)["\']?\s*(?:pulgadas?)?', title)
    if size_match:
        entities.size = f'{size_match.group(1)}"'
    
    # Resolución
    if 'fullhd' in title_lower or '1080p' in title_lower or 'fhd' in title_lower:
        entities.resolution = "Full HD"
    elif '4k' in title_lower or '2160p' in title_lower or 'uhd' in title_lower:
        entities.resolution = "4K"
    elif 'qhd' in title_lower or '1440p' in title_lower or 'wqhd' in title_lower:
        entities.resolution = "QHD"
    
    # Frecuencia de refresco
    hz_match = re.search(r'(\d{2,3})\s*hz', title_lower)
    if hz_match:
        entities.refresh_rate = f"{hz_match.group(1)}Hz"
    
    # Tipo de panel
    if 'ips' in title_lower:
        entities.panel_type = "IPS"
    elif 'va' in title_lower:
        entities.panel_type = "VA"
    elif 'oled' in title_lower:
        entities.panel_type = "OLED"
    elif 'tn' in title_lower:
        entities.panel_type = "TN"
    
    # RAM
    ram_match = re.search(r'(\d{1,2})\s*gb\s*(?:ram|ddr)', title_lower)
    if ram_match:
        entities.memory = f"{ram_match.group(1)}GB"
    
    # Almacenamiento
    storage_match = re.search(r'(\d{3,4})\s*gb\s*(?:ssd|hdd|nvme)?|(\d)\s*tb', title_lower)
    if storage_match:
        if storage_match.group(1):
            entities.storage = f"{storage_match.group(1)}GB"
        elif storage_match.group(2):
            entities.storage = f"{storage_match.group(2)}TB"
    
    if current_price:
        entities.price_detected = current_price
        entities.price_confidence = "medium"
    
    return entities


def batch_extract_entities(
    products: List[Dict[str, Any]],
    api_key: str,
    provider: str = "anthropic",
    progress_callback=None
) -> List[ProductEntities]:
    """
    Extrae entidades de múltiples productos.
    
    Args:
        products: Lista de dicts con 'title' y opcionalmente 'price'
        api_key: API key
        provider: "anthropic" o "openai"
        progress_callback: Función para reportar progreso (i, total)
    
    Returns:
        Lista de ProductEntities
    """
    results = []
    total = len(products)
    
    for i, product in enumerate(products):
        title = product.get('title', '')
        price = product.get('price')
        
        entities = extract_entities_with_llm(title, price, api_key, provider)
        results.append(entities)
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    return results
