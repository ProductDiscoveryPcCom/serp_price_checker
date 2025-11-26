import streamlit as st
import requests
import json
from src import (
    scrape_google_serp,
    extract_prices_with_claude,
    extract_prices_with_openai,
    build_analysis,
    SPANISH_CITIES,
    parse_extension_csv,
)
from src.models import MatchedProduct

# Configuración de página
st.set_page_config(
    page_title="SERP Price Checker",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 SERP Price Checker")
st.markdown("Analiza tu competitividad de precios en **Google España** 🇪🇸")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Método de obtención de datos
    st.markdown("### 📊 Fuente de datos")
    data_source = st.radio(
        "¿Cómo obtener los datos?",
        ["📁 Subir CSV (extensión Chrome)", "🌐 ZenRows API (automático)"],
        help="El CSV de la extensión Chrome es más preciso para España"
    )
    
    use_csv = data_source.startswith("📁")
    
    if not use_csv:
        zenrows_key = st.text_input(
            "ZenRows API Key",
            value=st.secrets.get("ZENROWS_API_KEY", ""),
            type="password"
        )
        
        st.divider()
        st.markdown("### 📍 Ubicación")
        selected_city = st.selectbox(
            "Simular búsqueda desde",
            options=list(SPANISH_CITIES.keys()),
            index=0,
            help="Los resultados de Google varían según la ubicación"
        )
    
    st.divider()
    st.markdown("### 🤖 Análisis con IA")
    
    # Solo necesitamos LLM si usamos ZenRows (para extraer precios del JSON)
    if not use_csv:
        llm_provider = st.selectbox(
            "Proveedor LLM",
            ["Claude (Anthropic)", "GPT (OpenAI)"]
        )
        
        if llm_provider == "Claude (Anthropic)":
            llm_key = st.text_input(
                "Anthropic API Key",
                value=st.secrets.get("ANTHROPIC_API_KEY", ""),
                type="password"
            )
        else:
            llm_key = st.text_input(
                "OpenAI API Key", 
                value=st.secrets.get("OPENAI_API_KEY", ""),
                type="password"
            )
    else:
        llm_provider = None
        llm_key = None
    
    st.divider()
    st.markdown("### 🏪 Tu tienda")
    your_domain = st.text_input(
        "Tu dominio",
        placeholder="mitienda.es"
    )

# Formulario principal
st.markdown("---")

col1, col2 = st.columns([3, 1])

with col1:
    product_query = st.text_input(
        "🔎 Producto a analizar",
        placeholder="Xiaomi Mi Smart Projector 2"
    )

with col2:
    your_price = st.number_input(
        "💰 Tu precio (€)",
        min_value=0.0,
        step=0.01,
        format="%.2f"
    )

# Subida de CSV si está seleccionada esa opción
uploaded_file = None
if use_csv:
    st.markdown("### 📁 Subir CSV de la extensión")
    st.info("""
    **Cómo obtener el CSV:**
    1. Busca el producto en Google.es
    2. Haz clic en la extensión "Google Rank Checker"
    3. Exporta a CSV
    4. Sube el archivo aquí
    """)
    uploaded_file = st.file_uploader(
        "Arrastra el CSV aquí",
        type=["csv", "txt"],
        help="Archivo CSV exportado de la extensión Chrome"
    )

# Botón de análisis
if st.button("🚀 Analizar competencia", type="primary", use_container_width=True):
    
    # Validaciones comunes
    if not product_query:
        st.error("❌ Introduce el nombre del producto")
        st.stop()
    if not your_domain:
        st.error("❌ Introduce tu dominio")
        st.stop()
    if your_price <= 0:
        st.error("❌ Introduce tu precio")
        st.stop()
    
    # Validaciones específicas por método
    if use_csv and not uploaded_file:
        st.error("❌ Sube el archivo CSV de la extensión")
        st.stop()
    
    if not use_csv:
        if not zenrows_key:
            st.error("❌ Falta la API Key de ZenRows")
            st.stop()
        if not llm_key:
            st.error(f"❌ Falta la API Key de {llm_provider}")
            st.stop()
    
    products = []
    
    # Proceso de análisis
    with st.status("Analizando...", expanded=True) as status:
        
        # ============================================
        # OPCIÓN 1: Usar CSV de la extensión Chrome
        # ============================================
        if use_csv:
            st.write("📁 Procesando CSV de la extensión...")
            try:
                # Leer contenido del CSV
                csv_content = uploaded_file.read().decode('utf-8')
                
                # Parsear CSV
                csv_results = parse_extension_csv(csv_content)
                
                st.write(f"✅ {len(csv_results)} productos con precio encontrados")
                
                # Convertir a MatchedProduct
                for item in csv_results:
                    products.append(MatchedProduct(
                        title=item['title'],
                        price=item['price'],
                        store=item['store'],
                        url=item['url'],
                        match_confidence=0.95 if 'Shopping' in item.get('type', '') else 0.8
                    ))
                
                # Debug
                if products:
                    with st.expander("🔍 Debug: Productos del CSV"):
                        for p in products[:15]:
                            st.write(f"**{p.store}**: {p.price:.2f}€ - {p.title[:50]}...")
                            
            except Exception as e:
                st.error(f"❌ Error procesando CSV: {str(e)}")
                st.stop()
        
        # ============================================
        # OPCIÓN 2: Usar ZenRows API
        # ============================================
        else:
            st.write(f"🔍 Buscando en Google.es desde {selected_city}...")
            try:
                serp_data = scrape_google_serp(
                    query=f"{product_query} precio comprar",
                    zenrows_api_key=zenrows_key,
                    num_results=20,
                    location=SPANISH_CITIES[selected_city]
                )
                
                num_organic = len(serp_data.get("organic_results", []))
                num_ads = len(serp_data.get("ad_results", []))
                st.write(f"✅ {num_organic} resultados orgánicos + {num_ads} anuncios")
                
                with st.expander("🔍 Debug: Resultados SERP"):
                    st.json(serp_data)
                            
            except requests.exceptions.HTTPError as e:
                st.error(f"❌ Error HTTP de ZenRows: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}")
                if hasattr(e, 'response'):
                    st.code(e.response.text[:500])
                st.stop()
            except Exception as e:
                st.error(f"❌ Error en búsqueda: {str(e)}")
                st.stop()
            
            if not serp_data.get("organic_results") and not serp_data.get("ad_results"):
                st.warning("⚠️ No se encontraron resultados")
                st.stop()
            
            # Extracción de precios con LLM
            st.write("🤖 Extrayendo precios con IA...")
            try:
                if llm_provider == "Claude (Anthropic)":
                    products = extract_prices_with_claude(
                        query=product_query,
                        serp_data=serp_data,
                        api_key=llm_key
                    )
                else:
                    products = extract_prices_with_openai(
                        query=product_query,
                        serp_data=serp_data,
                        api_key=llm_key
                    )
                
                st.write(f"✅ {len(products)} productos con precio encontrados")
                
                if products:
                    with st.expander("🔍 Debug: Productos extraídos"):
                        for p in products[:10]:
                            st.json({
                                "store": p.store,
                                "price": p.price,
                                "title": p.title[:60] + "..." if len(p.title) > 60 else p.title,
                            })
                            
            except Exception as e:
                st.error(f"❌ Error en extracción: {str(e)}")
                st.stop()
        
        # ============================================
        # Verificar que tenemos productos
        # ============================================
        if not products:
            st.warning("⚠️ No se encontraron productos con precios. Prueba con otro producto o términos de búsqueda más específicos.")
            st.stop()
        
        # ============================================
        # Construir análisis
        # ============================================
        st.write("📊 Generando análisis...")
        analysis = build_analysis(
            query=product_query,
            your_domain=your_domain,
            your_price=your_price,
            shopping_results=products
        )
        
        status.update(label="✅ Análisis completado", state="complete")
    
    # ============================================
    # Mostrar resultados
    # ============================================
    st.divider()
    st.header("📊 Resultados")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if analysis.your_serp_position:
            st.metric("📍 Tu posición", f"#{analysis.your_serp_position}")
        else:
            st.metric("📍 Tu posición", "No apareces", delta="❌", delta_color="off")
    
    with col2:
        total_competitors = len(analysis.competitors)
        st.metric(
            "💰 Ranking precio",
            f"#{analysis.your_price_position} de {total_competitors + 1}"
        )
    
    with col3:
        if analysis.competitors:
            cheapest = analysis.competitors[0].price
            diff = your_price - cheapest
            pct = (diff / cheapest) * 100 if cheapest else 0
            st.metric(
                "📉 vs Más barato",
                f"{diff:+.2f}€",
                delta=f"{pct:+.1f}%",
                delta_color="inverse"
            )
        else:
            st.metric("📉 vs Más barato", "N/A")
    
    with col4:
        st.metric("🔍 Competidores", len(analysis.competitors))
    
    # Tabla de competidores
    st.subheader("🏆 Ranking por precio")
    
    if analysis.competitors:
        table_data = []
        
        for i, comp in enumerate(analysis.competitors, 1):
            store_clean = comp.store.lower() if comp.store else ""
            url_clean = comp.url.lower() if comp.url else ""
            your_domain_clean = your_domain.replace('www.', '').lower()
            is_you = your_domain_clean in store_clean or your_domain_clean in url_clean
            
            table_data.append({
                "Pos.": i,
                "Tienda": comp.store or "Desconocida",
                "Precio": f"{comp.price:.2f}€",
                "Producto": comp.title[:50] + "..." if len(comp.title) > 50 else comp.title,
                "": "👈 TÚ" if is_you else ""
            })
        
        # Añadir tu posición si no apareces
        if not analysis.your_serp_position:
            your_entry = {
                "Pos.": analysis.your_price_position,
                "Tienda": your_domain,
                "Precio": f"{your_price:.2f}€",
                "Producto": "(Tu producto)",
                "": "👈 TÚ"
            }
            table_data.insert(analysis.your_price_position - 1, your_entry)
            for i, row in enumerate(table_data, 1):
                row["Pos."] = i
        
        st.dataframe(table_data, use_container_width=True, hide_index=True)
        
        # Insights
        st.subheader("💡 Insights")
        
        cheapest = analysis.competitors[0]
        most_expensive = analysis.competitors[-1]
        avg_price = sum(c.price for c in analysis.competitors) / len(analysis.competitors)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            **Rango de precios:**
            - 🟢 Más barato: **{cheapest.price:.2f}€** ({cheapest.store})
            - 🔴 Más caro: **{most_expensive.price:.2f}€** ({most_expensive.store})
            - 📊 Media: **{avg_price:.2f}€**
            """)
        
        with col2:
            diff_to_avg = your_price - avg_price
            diff_to_min = your_price - cheapest.price
            
            if diff_to_avg < 0:
                st.success(f"✅ Estás **{abs(diff_to_avg):.2f}€ por debajo** de la media")
            else:
                st.warning(f"⚠️ Estás **{diff_to_avg:.2f}€ por encima** de la media")
            
            if analysis.your_price_position == 1:
                st.success("🏆 ¡Tienes el mejor precio!")
            elif analysis.your_price_position <= 3:
                st.info("👍 Estás en el top 3 por precio")
            else:
                st.warning(f"💡 Para ser el más barato, baja **{diff_to_min:.2f}€**")
    else:
        st.info("No se encontraron competidores con precios")

# Footer
st.divider()
st.caption("🔍 Datos de Google.es • CSV de extensión Chrome o ZenRows SERP API")
