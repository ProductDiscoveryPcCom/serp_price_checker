# 🔍 SERP Price Checker

Herramienta para analizar la competitividad de precios de tus productos en **Google España** 🇪🇸

## ✨ Características

- **Dos modos de obtención de datos:**
  - 📁 **CSV de extensión Chrome** (recomendado): Datos reales de tu navegador
  - 🌐 **ZenRows API**: Búsqueda automática (fallback)
- **Análisis de Shopping Ads** con precios reales de tiendas españolas
- **Ranking por precio** vs competidores
- **Insights** sobre tu posición competitiva
- **Selector de ciudades** para búsquedas localizadas

## 🚀 Despliegue

### Streamlit Cloud

1. Sube este repositorio a GitHub
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repositorio
4. **Main file path**: `app.py`
5. Configura los secrets (solo si usas ZenRows):

```toml
ZENROWS_API_KEY = "tu_api_key"
ANTHROPIC_API_KEY = "tu_api_key"
```

### Local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📖 Uso

### Método 1: CSV de extensión Chrome ⭐ (recomendado)

1. Instala la extensión [Google Rank Checker](https://chrome.google.com/webstore/detail/hcghkofiggmpkedhjkpnpmaimfbbgfdo)
2. Busca tu producto en Google.es
3. Haz clic en la extensión y exporta a CSV
4. Sube el CSV a la app
5. ¡Analiza!

**Ventajas:**
- ✅ Datos 100% reales de tu ubicación en España
- ✅ Incluye Shopping Ads con precios exactos
- ✅ Sin límites de API
- ✅ Gratis

### Método 2: ZenRows API (automático)

1. Obtén API key en [zenrows.com](https://zenrows.com)
2. Configura las API keys
3. Introduce el producto y tu precio
4. ¡Analiza!

## 📊 Qué analiza

| Tipo | Descripción |
|------|-------------|
| Shopping Ads | Precios del carrusel de Google Shopping |
| Orgánicos | Tiendas en resultados normales con precio visible |
| Tu posición | Ranking de precio vs competencia |

## 🏪 Tiendas detectadas

Amazon.es, PCComponentes, MediaMarkt, Fnac, El Corte Inglés, Carrefour, Worten, Mi.com, y más tiendas españolas.

## 📁 Estructura

```
serp-price-checker/
├── app.py                 # Aplicación Streamlit
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml
└── src/
    ├── __init__.py
    ├── models.py          # Modelos de datos
    ├── scraper.py         # Parser CSV + ZenRows
    └── analyzer.py        # Extracción con LLM
```

## 🔧 Tecnologías

- **Streamlit**: Interfaz web
- **ZenRows**: API SERP (opcional)
- **Claude/GPT**: Extracción de precios (solo modo ZenRows)

## 📝 Licencia

MIT
