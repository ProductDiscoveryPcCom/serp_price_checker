# 🔍 SERP Price Checker v4

Herramienta profesional de análisis de precios competitivos en **Google Shopping España**.

## ✨ Novedades v4

### 🎯 Matching inteligente por especificaciones
- Compara productos por CPU, GPU, RAM, no por texto
- Detecta productos equivalentes de diferentes tiendas
- Clustering automático por categoría de producto

### 💡 Recomendaciones accionables
- "Baja 50€ para entrar en top 3"
- "Tienes margen de subida de 30€"
- "⚠️ 3 competidores con ofertas agresivas"

### 📊 Visualización mejorada
- Gráfico de distribución de precios
- Tu posición marcada visualmente
- Diferencia en € y % vs tu precio
- Badge de ofertas 🏷️

### 📥 Exportación
- CSV y Excel
- Formato con colores (Excel)

## 🚀 Instalación

### Streamlit Cloud (recomendado)
1. Fork este repositorio
2. Conecta en [share.streamlit.io](https://share.streamlit.io)
3. Main file: `app.py`
4. Secrets (opcional):
```toml
ANTHROPIC_API_KEY = "sk-..."
OPENAI_API_KEY = "sk-..."
```

### Local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Obtener datos

1. Instala [Google Rank Checker](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)
2. Busca tu producto en Google.es
3. Clic en la extensión → Exportar CSV
4. Sube el CSV

## 🔧 Arquitectura

```
serp-v4/
├── app.py                  # UI principal
├── requirements.txt
├── .streamlit/config.toml
└── src/
    ├── core/
    │   ├── models.py       # Modelos de datos
    │   ├── matcher.py      # Matching por specs
    │   └── analyzer.py     # Análisis y recomendaciones
    ├── data/
    │   └── parser.py       # Parseo de CSV
    └── services/
        └── llm_service.py  # Integración LLM
```

## 📊 Tipos de matching

| Nivel | Descripción | Ejemplo |
|-------|-------------|---------|
| ✅ Exacto | Mismo modelo | MSI Cyborg 15 B13WFKG-687XES |
| 🔷 Equivalente | Mismas specs | Mismo CPU/GPU/RAM, diferente SKU |
| 🔶 Similar | Misma gama | MSI Cyborg vs MSI Thin (mismo tier) |
| ⚪ Diferente | Otro producto | MSI Cyborg vs Lenovo Legion |

## 🤖 Opciones de procesamiento

| Opción | Descripción | Precisión | Coste |
|--------|-------------|-----------|-------|
| 🐍 Default | Regex | Media | Gratis |
| 🤖 Claude | Anthropic | Alta | ~$0.01/análisis |
| 🧠 GPT | OpenAI | Alta | ~$0.005/análisis |
| 🔀 Mixto | Ambos | Muy alta | ~$0.015/análisis |

## 💡 Recomendaciones generadas

- **Reducción de precio**: Cuánto bajar para mejorar ranking
- **Subida de precio**: Si tienes margen vs competencia
- **Alertas**: Ofertas agresivas de competidores
- **Oportunidades**: Múltiples productos posicionados

## 📈 Métricas

- Posición SERP
- Ranking de precio (global y por cluster)
- Diferencia vs más barato
- Diferencia vs media
- Productos más baratos/caros que tú

## 🔗 Links

- [Extensión Chrome](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)
- [Anthropic](https://console.anthropic.com/)
- [OpenAI](https://platform.openai.com/)

## 📝 Changelog

### v4.0.0
- Matching por especificaciones (no por texto)
- Clustering de productos
- Recomendaciones accionables
- Gráfico de distribución
- Exportación a Excel
- Arquitectura modular
- Logging y caché

### v3.0.0
- Separación por tipo de resultado
- Badge de ofertas
- Diferencia € y %

### v2.0.0
- Parser CSV mejorado
- Detección de ofertas
- Múltiples LLMs
