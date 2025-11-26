# 🔍 SERP Price Checker

Analiza tu competitividad de precios en **Google España** 🇪🇸

## ✨ Dos modos de uso

### 📁 CSV de extensión Chrome (recomendado)
- Datos 100% reales de tu navegador
- Incluye Shopping Ads con precios exactos
- Sin límites de API, gratis

### 🌐 ZenRows API (automático)
- Búsqueda automática
- Requiere API keys

## 🚀 Despliegue en Streamlit Cloud

1. Sube estos archivos a GitHub
2. Conecta en [share.streamlit.io](https://share.streamlit.io)
3. Main file: `app.py`

### Secrets (solo para ZenRows)
```toml
ZENROWS_API_KEY = "..."
ANTHROPIC_API_KEY = "..."
```

## 📖 Uso con CSV

1. Instala [Google Rank Checker](https://chrome.google.com/webstore/detail/hcghkofiggmpkedhjkpnpmaimfbbgfdo)
2. Busca tu producto en Google.es
3. Exporta CSV con la extensión
4. Sube el CSV a la app

## 📁 Estructura

```
├── app.py
├── requirements.txt
├── .streamlit/config.toml
└── src/
    ├── __init__.py
    ├── models.py
    ├── scraper.py
    └── analyzer.py
```
