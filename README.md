# 🔍 SERP Price Checker

Herramienta para analizar tu competitividad de precios en **Google España** 🇪🇸

## ✨ Funcionalidades

### 📊 Análisis de datos
- **Separación por tipo**: Shopping Ads, Organic, Ads, Ads Sub
- **Detección de ofertas**: Muestra precio original vs precio actual
- **Match de productos**: Exacto (≥85%), Parcial (60-85%), Diferente (<60%)
- **Diferencia de precio**: % respecto a tu precio (🟢 más barato, 🔴 más caro)

### 🏪 Tu tienda
- Muestra todos los productos de tu tienda que aparecen en la búsqueda
- Detecta múltiples productos de tu dominio

### 🤖 Procesamiento con LLM
- **Default (Python)**: Extracción con regex, sin API
- **Claude (Anthropic)**: Extracción inteligente de características
- **GPT (OpenAI)**: Alternativa con OpenAI
- **Mixto**: Combina ambos LLMs

### 🕷️ Scraping avanzado (opcional)
- Agente que scrapea URLs individuales con ZenRows
- Extrae información detallada de cada producto

### 📋 Características del producto
- Marca, Modelo
- Procesador (Intel/AMD)
- RAM, Almacenamiento
- GPU (NVIDIA/AMD)
- Pantalla, Sistema Operativo

### 📥 Exportación
- Exportar cada tipo a CSV
- Exportar análisis completo

## 🚀 Instalación

### Opción 1: Streamlit Cloud (recomendado)

1. Sube los archivos a un repositorio GitHub
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repositorio
4. Main file path: `app.py`
5. (Opcional) Configura secrets:

```toml
ZENROWS_API_KEY = "tu_key"
ANTHROPIC_API_KEY = "tu_key"
OPENAI_API_KEY = "tu_key"
```

### Opción 2: Local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Obtener datos (CSV de extensión Chrome)

1. Instala la extensión [Google Rank Checker](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)
2. Busca tu producto en Google.es
3. Haz clic en la extensión
4. Exporta a CSV
5. Sube el CSV a la aplicación

## 📂 Estructura

```
serp-price-checker/
├── app.py              # Aplicación principal
├── requirements.txt    # Dependencias
├── README.md
├── .streamlit/
│   └── config.toml
└── src/
    ├── __init__.py
    ├── models.py       # Modelos de datos
    ├── scraper.py      # Parser CSV y scraping
    └── analyzer.py     # Análisis y LLM
```

## 🔧 Tipos de resultado

| Tipo | Descripción | Tiene precio |
|------|-------------|--------------|
| Shopping Ads | Anuncios de Google Shopping | ✅ Sí |
| Organic | Resultados orgánicos | ❌ No (solo apariciones) |
| Ads | Anuncios de texto | ❌ No (solo apariciones) |
| Ads Sub | Sub-enlaces de anuncios | ❌ No (solo apariciones) |

## 📝 Notas

- Los resultados **Organic** y **Ads** aparecen como listados generales sin precio
- El análisis de precios solo incluye productos con precio (Shopping Ads)
- El LLM extrae características más precisas que el regex por defecto
- El agente de scraping consume créditos de ZenRows

## 🔗 Enlaces

- [Extensión Chrome](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)
- [ZenRows](https://www.zenrows.com/)
- [Anthropic](https://console.anthropic.com/)
- [OpenAI](https://platform.openai.com/)
