# 🔍 SERP Price Checker

Herramienta para analizar la competitividad de precios de tus productos en **Google Shopping** España.

## ✨ Características

- **Scraping de Google Shopping**: Obtiene productos del carrusel de Shopping con precios reales
- **Extracción con IA**: Usa Claude o GPT para parsear el HTML y extraer productos estructurados
- **Análisis de precios**: Compara tu precio con la competencia
- **Posicionamiento**: Muestra tu posición en el ranking por precio

## 🛠️ Cómo funciona

```
┌─────────────────────────────────────────────────────────────┐
│  1. INPUT: Producto + Tu precio + Tu dominio                │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ZenRows Universal Scraper                               │
│     → Obtiene HTML de Google Shopping España                │
│     → URL: google.es/search?q={producto}&tbm=shop           │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Claude/GPT parsea el HTML                               │
│     → Extrae: producto, precio, tienda                      │
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
5. Configura los secrets (ver abajo)
6. ¡Deploy!

### Configurar Secrets

En Streamlit Cloud, ve a **Settings > Secrets** y añade:

```toml
ZENROWS_API_KEY = "tu-api-key-de-zenrows"
ANTHROPIC_API_KEY = "tu-api-key-de-anthropic"
OPENAI_API_KEY = "tu-api-key-de-openai"
```

## 🛠️ Desarrollo local

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/serp-price-checker.git
cd serp-price-checker

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar secrets localmente
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
ZENROWS_API_KEY = "tu-api-key"
ANTHROPIC_API_KEY = "tu-api-key"
OPENAI_API_KEY = "tu-api-key"
EOF

# Ejecutar
streamlit run app.py
```

## 📋 Uso

1. Introduce el producto a buscar (ej: "Samsung Galaxy S24 Ultra 256GB")
2. Introduce tu dominio/nombre de tienda (ej: "mitienda.es" o "Mi Tienda")
3. Introduce tu precio actual
4. Haz clic en "Analizar competencia"

## 📊 Output

- **Ranking por precio**: Lista ordenada de competidores con sus precios
- **Tu posición**: Dónde estarías tú en el ranking
- **Insights**: 
  - Precio más bajo, más alto y media del mercado
  - Cuánto deberías bajar para ser el más competitivo

## ⚠️ Requisitos de API

| API | Uso | Notas |
|-----|-----|-------|
| ZenRows | Scraping Google Shopping | Necesita plan con JS rendering |
| Anthropic | Parseo de HTML | Claude Sonnet |
| OpenAI | Parseo de HTML (alternativa) | GPT-4o-mini |

## 🗺️ Roadmap

- [ ] Histórico de precios y alertas
- [ ] Soporte multi-país
- [ ] Exportar resultados a CSV/Excel
- [ ] Comparativa con resultados orgánicos
- [ ] API REST

## 📄 Licencia

MIT
