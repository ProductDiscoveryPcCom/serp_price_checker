# 🔍 SERP Price Checker v4.2

Herramienta de análisis de precios competitivos en **Google Shopping España**.

**Funciona para cualquier tipo de producto** - portátiles, móviles, electrodomésticos, monitores, consolas, etc.

## ✨ Características

### 🎯 Matching genérico por tokens
- Compara productos por palabras clave y marcas
- Detecta automáticamente +150 marcas conocidas
- Sinónimos integrados (PS5 = PlayStation 5, iPhone = Apple, etc.)

### 🔗 Identificación precisa de tu producto
- Por URL exacta (más preciso)
- Por dominio + precio (fallback)
- Detecta automáticamente tu posición SERP

### 🏪 Tus productos con pestañas
- Navegación por tipo: Shopping Ads, Organic, Ads
- Columna de tienda/dominio visible
- Match visual con iconos y porcentajes

### 🤖 Agente IA (opcional)
Activa el agente para extraer entidades automáticamente de los títulos:
- **Marca**: MSI, Samsung, Sony, etc.
- **Modelo**: MAG 274F, Galaxy S24, etc.
- **Tamaño**: 27", 15.6", etc.
- **Resolución**: Full HD, 4K, QHD
- **Panel**: IPS, VA, OLED
- **Frecuencia**: 144Hz, 200Hz
- **Memoria/Almacenamiento**: 16GB, 1TB SSD
- **Color**, **Conectividad**, y más...

También verifica precios y avisa si detecta discrepancias.

**Proveedores soportados:**
- Anthropic (Claude)
- OpenAI (GPT-4)

### 💡 Recomendaciones accionables
- "Baja 50€ para entrar en top 3"
- "Tienes margen de subida de 30€"
- "⚠️ Competidores con ofertas agresivas"
- "🎯 Producto muy similar más barato"

### 📊 Visualización
- Gráfico de distribución de precios
- Tu posición marcada
- Diferencia en € y %
- Badge de ofertas 🏷️

### 💰 Parser de precios robusto
- Formato español: 1.299,00 €
- Formato americano: 1,299.00 €
- Formato simple: 599,99 € / 599.99 €
- Céntimos: 94900 € → 949.00€
- Detecta ofertas automáticamente

## 🚀 Instalación

### Streamlit Cloud
1. Sube los archivos a GitHub
2. Conecta en [share.streamlit.io](https://share.streamlit.io)
3. Main file: `app.py`

### Local
```bash
pip install -r requirements.txt
streamlit run app.py

# Opcional: para usar el agente IA
pip install anthropic openai
```

## 📁 Obtener datos

1. Instala [Google Rank Checker](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)
2. Busca tu producto en Google.es
3. Clic en la extensión → Exportar CSV
4. Sube el CSV a la app

## ⚙️ Configuración

### Tu producto
- **Dominio**: tu-tienda.es (obligatorio)
- **URL**: https://tu-tienda.es/producto (opcional, más preciso)
- **Precio**: tu precio actual en €

### Opciones
- Mostrar todos los productos (incluye resultados sin precio)

### Agente IA (opcional)
- Activa el análisis con IA
- Selecciona proveedor (Anthropic/OpenAI)
- Introduce tu API key

## 📊 Niveles de matching

| Nivel | Score | Descripción |
|-------|-------|-------------|
| ✅ Exacto | >90% | Mismo producto |
| 🔷 Muy similar | 75-90% | Casi idéntico |
| 🔶 Similar | 50-75% | Similar |
| 🟡 Relacionado | 30-50% | Relacionado |
| ⚪ Diferente | <30% | Diferente |

## 🏷️ Marcas detectadas

+150 marcas incluyendo:

- **Tecnología**: Apple, Samsung, Xiaomi, Sony, LG, ASUS, Lenovo, HP, Dell, MSI, Gigabyte, Razer...
- **Gaming**: Nintendo, PlayStation, Xbox, Corsair, Logitech, SteelSeries, Newskill...
- **Electrodomésticos**: Bosch, Siemens, Cecotec, Dyson, Roomba, Roborock, Delonghi...
- **Movilidad**: Garmin, Segway, Fitbit, Youin, Nilox, Xiaomi...

## 🔧 Estructura

```
serp-v4/
├── app.py                    # UI principal
├── requirements.txt          # Dependencias
├── .streamlit/config.toml    # Configuración
└── src/
    ├── core/
    │   ├── models.py         # Modelos de datos
    │   ├── token_matcher.py  # Matching genérico
    │   └── analyzer.py       # Análisis + recomendaciones
    ├── data/
    │   └── parser.py         # Parser CSV + precios
    └── services/
        └── llm_service.py    # Agente IA para entidades
```

## 📝 Changelog

### v4.2.0
- ✅ Pestañas por tipo en "Tus productos" (Shopping, Organic, Ads)
- ✅ Columna de tienda/dominio visible
- ✅ Agente IA opcional para extracción de entidades
- ✅ Verificación de precios con IA
- ✅ Soporte Anthropic y OpenAI

### v4.1.0
- ✅ Identificación por URL exacta
- ✅ Parser de precios mejorado (más formatos)
- ✅ Eliminadas columnas CPU/GPU/RAM (genérico)
- ✅ Filtro de precios outliers

### v4.0.0
- Matching genérico por tokens
- +150 marcas detectadas
- Sinónimos integrados
- Arquitectura modular
