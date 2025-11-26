"""Servicio de LLM para extracción de características."""

import json
import re
import logging
import hashlib
from typing import List, Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Caché simple en memoria
_llm_cache: Dict[str, dict] = {}


def _get_cache_key(titles: List[str], provider: str) -> str:
    """Genera clave de caché única."""
    content = json.dumps(sorted(titles)) + provider
    return hashlib.md5(content.encode()).hexdigest()


def extract_features_batch(
    titles: List[str],
    provider: str,
    api_key: str,
    api_key_2: Optional[str] = None,
    batch_size: int = 15
) -> List[dict]:
    """
    Extrae características de productos usando LLM.
    
    Args:
        titles: Lista de títulos de productos
        provider: "claude", "openai", "mixto" o "default"
        api_key: API key principal
        api_key_2: API key secundaria (para mixto)
        batch_size: Productos por llamada LLM
        
    Returns:
        Lista de diccionarios con características
    """
    if provider == "default" or not api_key:
        return [{}] * len(titles)
    
    # Verificar caché
    cache_key = _get_cache_key(titles, provider)
    if cache_key in _llm_cache:
        logger.info("Usando caché de LLM")
        return _llm_cache[cache_key]
    
    results = []
    
    # Procesar en batches
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        
        try:
            if "claude" in provider.lower():
                batch_results = _extract_with_claude(batch, api_key)
            elif "openai" in provider.lower() or "gpt" in provider.lower():
                batch_results = _extract_with_openai(batch, api_key_2 or api_key)
            elif "mixto" in provider.lower():
                # Usar Claude para la primera mitad, OpenAI para la segunda
                mid = len(batch) // 2
                batch_results = (
                    _extract_with_claude(batch[:mid], api_key) +
                    _extract_with_openai(batch[mid:], api_key_2 or api_key)
                )
            else:
                batch_results = [{}] * len(batch)
            
            results.extend(batch_results)
            
        except Exception as e:
            logger.error(f"Error en batch LLM: {e}")
            results.extend([{}] * len(batch))
    
    # Guardar en caché
    _llm_cache[cache_key] = results
    
    return results


def _extract_with_claude(titles: List[str], api_key: str) -> List[dict]:
    """Extrae características usando Claude."""
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic no instalado")
        return [{}] * len(titles)
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Analiza estos títulos de portátiles/laptops y extrae características técnicas.

TÍTULOS:
{json.dumps(titles, ensure_ascii=False, indent=2)}

Para cada uno extrae (JSON array):
- brand: Marca
- series: Serie/línea (Cyborg, Thin, ROG, Legion...)
- model: Código modelo (B13WFKG-687XES)
- processor: Procesador completo
- processor_gen: Generación (12th Gen, 13th Gen, Ryzen 7000...)
- ram_gb: GB de RAM (número)
- storage_gb: GB almacenamiento (número, 1TB=1000)
- gpu: GPU (RTX 4060, etc)
- gpu_tier: Tier (RTX 50xx, RTX 40xx, RTX 30xx...)
- screen_size: Pulgadas (número)
- os: Sistema operativo

Responde SOLO JSON array. Si no encuentras dato, usa "" o 0.

JSON:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        return json.loads(text)
        
    except Exception as e:
        logger.error(f"Error Claude: {e}")
        return [{}] * len(titles)


def _extract_with_openai(titles: List[str], api_key: str) -> List[dict]:
    """Extrae características usando OpenAI."""
    try:
        import openai
    except ImportError:
        logger.error("openai no instalado")
        return [{}] * len(titles)
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""Extrae características de estos portátiles.

TÍTULOS:
{json.dumps(titles, ensure_ascii=False)}

Extrae: brand, series, model, processor, processor_gen, ram_gb, storage_gb, gpu, gpu_tier, screen_size, os
Responde JSON array. Valores vacíos: "" o 0.

JSON:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # Puede venir como array o como objeto con key
        if isinstance(data, list):
            return data
        return data.get('products', data.get('items', data.get('results', [{}] * len(titles))))
        
    except Exception as e:
        logger.error(f"Error OpenAI: {e}")
        return [{}] * len(titles)


def apply_llm_features(products: list, features: List[dict]) -> list:
    """Aplica características extraídas por LLM a los productos."""
    for i, product in enumerate(products):
        if i >= len(features):
            break
        
        f = features[i]
        if not f:
            continue
        
        specs = product.specs
        
        # Aplicar solo si el LLM encontró algo mejor
        if f.get('brand'):
            specs.brand = f['brand']
        if f.get('series'):
            specs.series = f['series']
        if f.get('model'):
            specs.model_code = f['model']
        if f.get('processor'):
            specs.processor = f['processor']
        if f.get('processor_gen'):
            specs.processor_gen = f['processor_gen']
        if f.get('ram_gb'):
            specs.ram_gb = int(f['ram_gb']) if isinstance(f['ram_gb'], (int, float)) else specs.ram_gb
        if f.get('storage_gb'):
            specs.storage_gb = int(f['storage_gb']) if isinstance(f['storage_gb'], (int, float)) else specs.storage_gb
        if f.get('gpu'):
            specs.gpu = f['gpu']
        if f.get('gpu_tier'):
            specs.gpu_tier = f['gpu_tier']
        if f.get('screen_size'):
            specs.screen_size = float(f['screen_size']) if isinstance(f['screen_size'], (int, float)) else specs.screen_size
        if f.get('os'):
            specs.os = f['os']
    
    return products


def clear_cache():
    """Limpia la caché de LLM."""
    global _llm_cache
    _llm_cache = {}
    logger.info("Caché de LLM limpiada")
