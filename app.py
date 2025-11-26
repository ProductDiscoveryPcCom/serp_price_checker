import streamlit as st
import re
import pandas as pd
from difflib import SequenceMatcher
from src import (
    scrape_google_serp,
    parse_extension_csv,
    group_by_store,
    extract_features_with_claude,
    extract_features_with_openai,
    extract_prices_with_claude,
    extract_prices_with_openai,
    agent_scrape_and_extract,
    build_analysis,
    SPANISH_CITIES,
    ShoppingResult,
)

# Configuración de página
st.set_page_config(
    page_title="SERP Price Checker",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 SERP Price Checker")
st.markdown("Analiza tu competitividad de precios en **Google España** 🇪🇸")


def calculate_similarity(text1: str, text2: str) -> float:
    """Calcula el porcentaje de similitud entre dos textos."""
    if not text1 or not text2:
        return 0.0
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    return round(SequenceMatcher(None, t1, t2).ratio() * 100, 1)


def classify_match(similarity: float) -> tuple[str, str]:
    """Clasifica el match según similitud."""
    if similarity >= 85:
        return "✅ Exacto", "success"
    elif similarity >= 60:
        return f"🔶 Parcial ({similarity:.0f}%)", "warning"
    else:
        return f"❌ Diferente ({similarity:.0f}%)", "error"


def calculate_price_diff(competitor_price: float, your_price: float) -> str:
    """Calcula diferencia porcentual de precio."""
    if your_price <= 0:
        return "-"
    diff = ((competitor_price - your_price) / your_price) * 100
    if diff > 0:
        return f"🔴 +{diff:.1f}%"
    elif diff < 0:
        return f"🟢 {diff:.1f}%"
    else:
        return "🟡 0%"


def convert_df_to_csv(df):
    """Convierte DataFrame a CSV."""
    return df.to_csv(index=False).encode('utf-8')


# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # TU TIENDA - PRIMERO
    st.markdown("### 🏪 Tu tienda")
    your_domain = st.text_input(
        "Tu dominio",
        placeholder="mitienda.es"
    )
    your_price = st.number_input(
        "💰 Tu precio (€)",
        min_value=0.0,
        step=0.01,
        format="%.2f"
    )
    
    st.divider()
    
    # Fuente de datos
    st.markdown("### 📊 Fuente de datos")
    data_source = st.radio(
        "¿Cómo obtener los datos?",
        ["📁 Subir CSV (extensión Chrome)", "🌐 ZenRows API (automático)"],
        help="El CSV de la extensión Chrome es más preciso"
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
            index=0
        )
    
    st.divider()
    
    # Proveedor LLM
    st.markdown("### 🤖 Procesamiento")
    llm_provider = st.selectbox(
        "Proveedor de análisis",
        ["🐍 Default (Python)", "🤖 Claude (Anthropic)", "🧠 GPT (OpenAI)", "🔀 Mixto"],
        help="LLM extrae características detalladas del producto"
    )
    
    llm_key = None
    llm_key_2 = None
    
    if "Claude" in llm_provider or "Mixto" in llm_provider:
        llm_key = st.text_input(
            "Anthropic API Key",
            value=st.secrets.get("ANTHROPIC_API_KEY", ""),
            type="password"
        )
    
    if "GPT" in llm_provider or "Mixto" in llm_provider:
        llm_key_2 = st.text_input(
            "OpenAI API Key",
            value=st.secrets.get("OPENAI_API_KEY", ""),
            type="password"
        )
    
    # Scraping con agentes
    st.divider()
    st.markdown("### 🕷️ Scraping avanzado")
    use_agent_scraping = st.checkbox(
        "Usar agente para scraping",
        help="Scrapea URLs individuales para obtener más detalles (requiere ZenRows + LLM)"
    )
    
    if use_agent_scraping:
        if not use_csv:
            agent_zenrows = zenrows_key
        else:
            agent_zenrows = st.text_input(
                "ZenRows API Key (para agente)",
                value=st.secrets.get("ZENROWS_API_KEY", ""),
                type="password"
            )


# =============================================
# FORMULARIO PRINCIPAL
# =============================================
st.markdown("---")

product_query = st.text_input(
    "🔎 Producto a analizar",
    placeholder="Portátil MSI Cyborg 15"
)

# Subida de CSV
uploaded_file = None
if use_csv:
    st.markdown("### 📁 Subir CSV de la extensión")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("""
        **Cómo obtener el CSV:**
        1. Busca el producto en Google.es
        2. Haz clic en la extensión "Google Rank Checker"
        3. Exporta a CSV
        """)
    with col2:
        st.link_button(
            "📥 Descargar extensión",
            "https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es",
            use_container_width=True
        )
    
    uploaded_file = st.file_uploader(
        "Selecciona el archivo CSV",
        type=["csv", "txt"]
    )


# =============================================
# BOTÓN DE ANÁLISIS
# =============================================
if st.button("🚀 Analizar competencia", type="primary", use_container_width=True):
    
    # Validaciones
    if not product_query:
        st.error("❌ Introduce el nombre del producto")
        st.stop()
    if not your_domain:
        st.error("❌ Introduce tu dominio")
        st.stop()
    if your_price <= 0:
        st.error("❌ Introduce tu precio")
        st.stop()
    if use_csv and not uploaded_file:
        st.error("❌ Sube el archivo CSV")
        st.stop()
    if not use_csv and not zenrows_key:
        st.error("❌ Falta ZenRows API Key")
        st.stop()
    
    # Validar LLM keys
    if "Claude" in llm_provider and not llm_key:
        st.error("❌ Falta Anthropic API Key")
        st.stop()
    if "GPT" in llm_provider and not llm_key_2:
        st.error("❌ Falta OpenAI API Key")
        st.stop()
    
    products_by_type = {
        "Shopping Ads": [],
        "Organic": [],
        "Ads": [],
        "Ads Sub": [],
    }
    all_products = []
    your_store_products = []
    
    your_domain_clean = your_domain.lower().replace('www.', '')
    
    # =============================================
    # PROCESO DE ANÁLISIS
    # =============================================
    with st.status("Analizando...", expanded=True) as status:
        
        # OPCIÓN CSV
        if use_csv:
            st.write("📁 Procesando CSV...")
            try:
                csv_content = uploaded_file.read().decode('utf-8')
                csv_results = parse_extension_csv(csv_content, include_type=True)
                st.write(f"✅ {len(csv_results)} productos encontrados en CSV")
                
                # Usar LLM para extraer características si está configurado
                if "Claude" in llm_provider and llm_key:
                    st.write("🤖 Extrayendo características con Claude...")
                    csv_results = extract_features_with_claude(csv_results, llm_key)
                elif "GPT" in llm_provider and llm_key_2:
                    st.write("🧠 Extrayendo características con GPT...")
                    csv_results = extract_features_with_openai(csv_results, llm_key_2)
                elif "Mixto" in llm_provider and llm_key:
                    st.write("🔀 Extrayendo características con Claude + GPT...")
                    csv_results = extract_features_with_claude(csv_results, llm_key)
                
                # Convertir a ShoppingResult
                for idx, item in enumerate(csv_results, 1):
                    product = ShoppingResult(
                        position=idx,
                        title=item.get('title', ''),
                        price=item.get('price', 0),
                        store=item.get('store', ''),
                        url=item.get('url', ''),
                        result_type=item.get('type', 'Other'),
                        original_price=item.get('original_price'),
                        is_offer=item.get('is_offer', False),
                        brand=item.get('brand', ''),
                        model=item.get('model', ''),
                        processor=item.get('processor', ''),
                        ram=item.get('ram', ''),
                        storage=item.get('storage', ''),
                        gpu=item.get('gpu', ''),
                        screen=item.get('screen', ''),
                        os=item.get('os', ''),
                    )
                    product.similarity = calculate_similarity(product_query, item.get('title', ''))
                    
                    # Clasificar por tipo
                    result_type = item.get('type', '')
                    if result_type in products_by_type:
                        products_by_type[result_type].append(product)
                    
                    all_products.append(product)
                    
                    # Detectar productos de TU tienda
                    store_lower = item.get('store', '').lower()
                    url_lower = item.get('url', '').lower()
                    if your_domain_clean in store_lower or your_domain_clean in url_lower:
                        your_store_products.append(product)
                
            except Exception as e:
                st.error(f"❌ Error procesando CSV: {str(e)}")
                st.stop()
        
        # OPCIÓN ZENROWS API
        else:
            st.write(f"🔍 Buscando en Google.es desde {selected_city}...")
            try:
                serp_data = scrape_google_serp(
                    query=f"{product_query} precio",
                    zenrows_api_key=zenrows_key,
                    num_results=20,
                    location=SPANISH_CITIES[selected_city]
                )
                st.write(f"✅ Datos SERP obtenidos")
                
                # Extraer con LLM
                if "Claude" in llm_provider:
                    products = extract_prices_with_claude(product_query, serp_data, llm_key)
                elif "GPT" in llm_provider:
                    products = extract_prices_with_openai(product_query, serp_data, llm_key_2)
                else:
                    products = []
                
                for p in products:
                    p.result_type = "Organic"
                    p.similarity = calculate_similarity(product_query, p.title)
                    products_by_type["Organic"].append(p)
                    all_products.append(p)
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.stop()
        
        # Scraping con agente
        if use_agent_scraping and all_products:
            agent_key = agent_zenrows if use_csv else zenrows_key
            if agent_key and (llm_key or llm_key_2):
                st.write("🕷️ Agente scrapeando URLs para más detalles...")
                urls_to_scrape = [p.url for p in all_products[:5] if p.url]
                
                provider = "claude" if llm_key else "openai"
                agent_results = agent_scrape_and_extract(
                    urls=urls_to_scrape,
                    zenrows_api_key=agent_key,
                    llm_provider=provider,
                    llm_api_key=llm_key or llm_key_2,
                    openai_api_key=llm_key_2
                )
                
                if agent_results:
                    st.write(f"✅ Agente obtuvo {len(agent_results)} productos adicionales")
        
        if not all_products:
            st.warning("⚠️ No se encontraron productos")
            st.stop()
        
        st.write("📊 Generando análisis...")
        analysis = build_analysis(
            query=product_query,
            your_domain=your_domain,
            your_price=your_price,
            shopping_results=all_products
        )
        
        status.update(label="✅ Análisis completado", state="complete")
    
    # =============================================
    # RESULTADOS
    # =============================================
    st.divider()
    st.header("📊 Resultados")
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    exact_matches = len([p for p in all_products if p.similarity >= 85])
    
    with col1:
        if analysis.your_serp_position:
            st.metric("📍 Tu posición SERP", f"#{analysis.your_serp_position}")
        else:
            st.metric("📍 Tu posición SERP", "No apareces")
    with col2:
        st.metric("💰 Ranking precio", f"#{analysis.your_price_position} de {len(all_products)+1}")
    with col3:
        st.metric("🔍 Total productos", len(all_products))
    with col4:
        st.metric("✅ Matches exactos", exact_matches)
    
    # =============================================
    # PRODUCTOS DE TU TIENDA
    # =============================================
    if your_store_products:
        st.subheader(f"🏪 Productos de {your_domain} en esta búsqueda")
        
        your_data = []
        for p in your_store_products:
            your_data.append({
                "Tipo": p.result_type,
                "Producto": p.title[:60] + "..." if len(p.title) > 60 else p.title,
                "Precio": f"{p.price:.2f}€",
                "Match": classify_match(p.similarity)[0],
                "Procesador": p.processor,
                "RAM": p.ram,
                "GPU": p.gpu,
                "URL": p.url
            })
        
        df_your = pd.DataFrame(your_data)
        st.dataframe(
            df_your,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("🔗", display_text="Ver"),
            }
        )
        
        if len(your_store_products) > 1:
            st.info(f"💡 Tienes **{len(your_store_products)} productos** apareciendo para esta búsqueda")
    
    # =============================================
    # TABS POR TIPO
    # =============================================
    st.subheader("📋 Resultados por Tipo")
    
    tab_names = []
    tab_data = []
    for type_name, prods in products_by_type.items():
        if prods:
            tab_names.append(f"{type_name} ({len(prods)})")
            tab_data.append((type_name, prods))
    
    if tab_names:
        tabs = st.tabs(tab_names)
        
        for i, tab in enumerate(tabs):
            with tab:
                type_name, prods = tab_data[i]
                
                # Separar productos con y sin precio
                with_price = [p for p in prods if p.price > 0]
                without_price = [p for p in prods if p.price == 0]
                
                table_data = []
                
                # Primero los que tienen precio (ordenados)
                for p in sorted(with_price, key=lambda x: x.price):
                    match_label, _ = classify_match(p.similarity)
                    price_diff = calculate_price_diff(p.price, your_price)
                    
                    is_you = your_domain_clean in p.store.lower() or your_domain_clean in p.url.lower()
                    
                    # Precio con oferta
                    price_str = f"{p.price:.2f}€"
                    if p.original_price and p.original_price > p.price:
                        price_str = f"~~{p.original_price:.2f}€~~ **{p.price:.2f}€**"
                    
                    table_data.append({
                        "": "👈 TÚ" if is_you else "",
                        "Tienda": p.store,
                        "Producto": p.title[:50] + "..." if len(p.title) > 50 else p.title,
                        "Precio": price_str,
                        "vs Tú": price_diff,
                        "Match": match_label,
                        "Procesador": p.processor,
                        "RAM": p.ram,
                        "GPU": p.gpu,
                        "Almac.": p.storage,
                        "🔗": p.url
                    })
                
                # Luego los sin precio (apariciones)
                for p in without_price:
                    is_you = your_domain_clean in p.store.lower() or your_domain_clean in p.url.lower()
                    
                    table_data.append({
                        "": "👈 TÚ" if is_you else "",
                        "Tienda": p.store,
                        "Producto": p.title[:50] + "..." if len(p.title) > 50 else p.title,
                        "Precio": "-",
                        "vs Tú": "-",
                        "Match": "-",
                        "Procesador": "-",
                        "RAM": "-",
                        "GPU": "-",
                        "Almac.": "-",
                        "🔗": p.url
                    })
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "🔗": st.column_config.LinkColumn("🔗", display_text="Ver"),
                            "Precio": st.column_config.TextColumn("Precio"),
                        }
                    )
                    
                    csv = convert_df_to_csv(df)
                    st.download_button(
                        f"📥 Exportar {type_name}",
                        csv,
                        f"serp_{type_name.lower().replace(' ', '_')}.csv",
                        "text/csv"
                    )
    
    # =============================================
    # TABLA GENERAL CON CARACTERÍSTICAS
    # =============================================
    st.subheader("📋 Tabla Completa con Características")
    
    # Separar productos con y sin precio
    products_with_price = [p for p in all_products if p.price > 0]
    products_without_price = [p for p in all_products if p.price == 0]
    
    all_data = []
    
    # Primero productos con precio (ordenados)
    for p in sorted(products_with_price, key=lambda x: x.price):
        match_label, _ = classify_match(p.similarity)
        price_diff = calculate_price_diff(p.price, your_price)
        is_you = your_domain_clean in p.store.lower() or your_domain_clean in p.url.lower()
        
        all_data.append({
            "": "👈" if is_you else "",
            "Tipo": p.result_type,
            "Tienda": p.store,
            "Producto": p.title[:45] + "..." if len(p.title) > 45 else p.title,
            "Precio": f"{p.price:.2f}€",
            "vs Tú": price_diff,
            "Match": match_label,
            "Marca": p.brand,
            "Procesador": p.processor,
            "RAM": p.ram,
            "GPU": p.gpu,
            "Almac.": p.storage,
            "Pantalla": p.screen,
            "SO": p.os,
            "URL": p.url
        })
    
    # Luego productos sin precio (apariciones)
    for p in products_without_price:
        is_you = your_domain_clean in p.store.lower() or your_domain_clean in p.url.lower()
        
        all_data.append({
            "": "👈" if is_you else "",
            "Tipo": p.result_type,
            "Tienda": p.store,
            "Producto": p.title[:45] + "..." if len(p.title) > 45 else p.title,
            "Precio": "-",
            "vs Tú": "-",
            "Match": "-",
            "Marca": "",
            "Procesador": "",
            "RAM": "",
            "GPU": "",
            "Almac.": "",
            "Pantalla": "",
            "SO": "",
            "URL": p.url
        })
    
    # Añadir tu producto si no apareces (solo en la sección de productos con precio)
    if not analysis.your_serp_position and products_with_price:
        # Calcular posición correcta en la lista de productos con precio
        insert_pos = 0
        for i, p in enumerate(sorted(products_with_price, key=lambda x: x.price)):
            if p.price >= your_price:
                insert_pos = i
                break
            insert_pos = i + 1
        
        all_data.insert(insert_pos, {
            "": "👈",
            "Tipo": "Tu tienda",
            "Tienda": your_domain,
            "Producto": product_query,
            "Precio": f"{your_price:.2f}€",
            "vs Tú": "🟡 0%",
            "Match": "✅ Exacto",
            "Marca": "",
            "Procesador": "",
            "RAM": "",
            "GPU": "",
            "Almac.": "",
            "Pantalla": "",
            "SO": "",
            "URL": ""
        })
    
    df_all = pd.DataFrame(all_data)
    st.dataframe(
        df_all,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("🔗", display_text="Ver"),
        }
    )
    
    csv_all = convert_df_to_csv(df_all)
    st.download_button(
        "📥 Exportar TODO a CSV",
        csv_all,
        "serp_analisis_completo.csv",
        "text/csv"
    )
    
    # =============================================
    # INSIGHTS
    # =============================================
    st.subheader("💡 Insights")
    
    # Solo productos con precio y similitud alta
    products_with_price = [p for p in all_products if p.price > 0]
    similar_products = [p for p in products_with_price if p.similarity >= 60]
    
    if similar_products:
        sorted_similar = sorted(similar_products, key=lambda x: x.price)
        cheapest = sorted_similar[0]
        expensive = sorted_similar[-1]
        avg = sum(p.price for p in sorted_similar) / len(sorted_similar)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Estadísticas (productos similares)")
            st.markdown(f"""
            | Métrica | Valor | Tienda |
            |---------|-------|--------|
            | 🟢 Más barato | **{cheapest.price:.2f}€** | {cheapest.store} |
            | 🔴 Más caro | **{expensive.price:.2f}€** | {expensive.store} |
            | 📊 Media | **{avg:.2f}€** | - |
            | 📈 Tu precio | **{your_price:.2f}€** | {your_domain} |
            """)
        
        with col2:
            st.markdown("### 🎯 Tu posición")
            
            prices_below = len([p for p in sorted_similar if p.price < your_price])
            your_rank = prices_below + 1
            pct_vs_avg = ((your_price - avg) / avg * 100) if avg > 0 else 0
            
            st.metric(
                "Ranking entre similares",
                f"#{your_rank} de {len(sorted_similar)+1}",
                delta=f"{pct_vs_avg:+.1f}% vs media"
            )
            
            diff_to_min = your_price - cheapest.price
            
            if your_rank == 1:
                st.success("🏆 ¡Tienes el mejor precio!")
            elif your_rank <= 3:
                st.info(f"👍 Top 3. Para ser #1: -{diff_to_min:.2f}€")
            else:
                st.warning(f"💡 Para ser más barato: -{diff_to_min:.2f}€")
    else:
        st.info("No hay suficientes productos similares para insights detallados")

# Footer
st.divider()
st.caption("🔍 SERP Price Checker • [Extensión Chrome](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)")
