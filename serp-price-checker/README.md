# 🔍 SERP Price Checker

Herramienta para analizar la competitividad de precios de tus productos en **Google España**.

## ✨ Características

- **SERP API de ZenRows**: Obtiene resultados de búsqueda estructurados (rápido y estable)
- **Extracción con IA**: Claude/GPT analiza los resultados y extrae precios de títulos y snippets
- **Análisis de precios**: Compara tu precio con la competencia
- **Ranking**: Muestra tu posición en el mercado

## 🛠️ Cómo funciona

```
┌─────────────────────────────────────────────────────────────┐
│  1. INPUT: Producto + Tu precio + Tu dominio                │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ZenRows SERP API                                        │
│     → Busca "{producto} precio comprar" en Google.es        │
│     → Devuelve JSON estructurado con resultados             │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Claude/GPT analiza los resultados                       │
│     → Extrae precios de títulos y snippets                  │
│     → Identifica tiendas: Amazon, MediaMarkt, etc.          │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. OUTPUT: Ranking por precio + insights                   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Despliegue en Streamlit Cloud

1. Haz fork de este repositorio
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repositorio
4. **Main file path**: `app.py`
5. Configura los secrets
6. ¡Deploy!

### Configurar Secrets

En Streamlit Cloud → **Settings > Secrets**:

```toml
ZENROWS_API_KEY = "tu-api-key-de-zenrows"
ANTHROPIC_API_KEY = "tu-api-key-de-anthropic"
OPENAI_API_KEY = "tu-api-key-de-openai"
```

## 🛠️ Desarrollo local

```bash
git clone https://github.com/tu-usuario/serp-price-checker.git
cd serp-price-checker

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Crear secrets
mkdir -p .streamlit
echo 'ZENROWS_API_KEY = "..."' >> .streamlit/secrets.toml
echo 'ANTHROPIC_API_KEY = "..."' >> .streamlit/secrets.toml

streamlit run app.py
```

## 📋 Uso

1. Introduce el producto (ej: "Samsung Galaxy S24 Ultra 256GB")
2. Tu dominio (ej: "mitienda.es")
3. Tu precio actual
4. Click en "Analizar competencia"

## 📊 Output

- **Ranking por precio**: Lista ordenada de competidores
- **Tu posición**: Dónde estarías en el ranking
- **Insights**: Precio más bajo, más alto, media del mercado

## ⚠️ Notas

- Los precios se extraen de los snippets/títulos de los resultados de búsqueda
- No todos los resultados incluyen precio visible
- Funciona mejor con productos de electrónica populares

## 📄 Licencia

MIT
