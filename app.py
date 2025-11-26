import streamlit as st
import requests
import json
import re
import pandas as pd
from difflib import SequenceMatcher
from src import (
    scrape_google_serp,
    extract_prices_with_claude,
    extract_prices_with_openai,
    build_analysis,
    SPANISH_CITIES,
    parse_extension_csv,
)
from src.models import ShoppingResult

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
    
    # Normalizar textos
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    
    # Calcular similitud
    ratio = SequenceMatcher(None, t1, t2).ratio()
    return round(ratio * 100, 1)


def classify_match(similarity: float) -> tuple[str, str]:
    """Clasifica el match según el porcentaje de similitud."""
    if similarity >= 85:
        return "✅ Exacto", "success"
    elif similarity >= 60:
        return f"🔶 Parcial ({similarity}%)", "warning"
    else:
        return f"❌ Diferente ({similarity}%)", "error"


def calculate_price_diff(competitor_price: float, your_price: float) -> str:
    """Calcula la diferencia porcentual de precio."""
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
    """Convierte DataFrame a CSV para descarga."""
    return df.to_csv(index=False).encode('utf-8')


# Sidebar para configuración
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
    
    # Proveedor LLM - Siempre visible
    st.markdown("### 🤖 Procesamiento")
    llm_provider = st.selectbox(
        "Proveedor de análisis",
        ["🐍 Default (Python)", "🤖 Claude (Anthropic)", "🧠 GPT (OpenAI)", "🔀 Mixto (Claude + GPT)"],
        help="Default usa Python puro, sin API de IA"
    )
    
    # Mostrar campos de API key según selección
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

# Formulario principal
st.markdown("---")

product_query = st.text_input(
    "🔎 Producto a analizar",
    placeholder="Xiaomi Mi Smart Projector 2"
)

# Subida de CSV si está seleccionada esa opción
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
        4. Haz clic en "Browse files" y selecciona el archivo
        """)
    with col2:
        st.link_button(
            "📥 Descargar extensión",
            "https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es",
            use_container_width=True
        )
    
    uploaded_file = st.file_uploader(
        "Selecciona el archivo CSV",
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
    
    # Validaciones específicas
    if use_csv and not uploaded_file:
        st.error("❌ Sube el archivo CSV de la extensión")
        st.stop()
    
    if not use_csv:
        if not zenrows_key:
            st.error("❌ Falta la API Key de ZenRows")
            st.stop()
    
    # Validar API keys si se necesitan
    if "Claude" in llm_provider and not llm_key:
        st.error("❌ Falta la API Key de Anthropic")
        st.stop()
    if "GPT" in llm_provider and not llm_key_2:
        st.error("❌ Falta la API Key de OpenAI")
        st.stop()
    if "Mixto" in llm_provider and (not llm_key or not llm_key_2):
        st.error("❌ Faltan las API Keys de Anthropic y OpenAI")
        st.stop()
    
    products_by_type = {
        "Shopping Ads": [],
        "Organic": [],
        "Ads": [],
        "Ads Sub": [],
        "Other": []
    }
    
    # Proceso de análisis
    with st.status("Analizando...", expanded=True) as status:
        
        # OPCIÓN 1: CSV de extensión Chrome
        if use_csv:
            st.write("📁 Procesando CSV de la extensión...")
            try:
                csv_content = uploaded_file.read().decode('utf-8')
                csv_results = parse_extension_csv(csv_content, include_type=True)
                
                st.write(f"✅ {len(csv_results)} productos encontrados")
                
                for idx, item in enumerate(csv_results, 1):
                    product = ShoppingResult(
                        position=idx,
                        title=item['title'],
                        price=item['price'],
                        store=item['store'],
                        url=item['url']
                    )
                    
                    # Añadir tipo y similitud como atributos extra
                    product.result_type = item.get('type', 'Other')
                    product.similarity = calculate_similarity(product_query, item['title'])
                    
                    # Clasificar por tipo
                    result_type = item.get('type', 'Other')
                    if 'Shopping' in result_type:
                        products_by_type["Shopping Ads"].append(product)
                    elif result_type == 'Organic':
                        products_by_type["Organic"].append(product)
                    elif 'Sub' in result_type:
                        products_by_type["Ads Sub"].append(product)
                    elif 'Ads' in result_type:
                        products_by_type["Ads"].append(product)
                    else:
                        products_by_type["Other"].append(product)
                            
            except Exception as e:
                st.error(f"❌ Error procesando CSV: {str(e)}")
                st.stop()
        
        # OPCIÓN 2: ZenRows API
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
                            
            except Exception as e:
                st.error(f"❌ Error en búsqueda: {str(e)}")
                st.stop()
            
            # Procesar con LLM o Python
            st.write("🤖 Extrayendo precios...")
            try:
                products = []
                
                if "Claude" in llm_provider:
                    products = extract_prices_with_claude(product_query, serp_data, llm_key)
                elif "GPT" in llm_provider:
                    products = extract_prices_with_openai(product_query, serp_data, llm_key_2)
                elif "Mixto" in llm_provider:
                    products_claude = extract_prices_with_claude(product_query, serp_data, llm_key)
                    products_gpt = extract_prices_with_openai(product_query, serp_data, llm_key_2)
                    seen_urls = set()
                    for p in products_claude + products_gpt:
                        if p.url not in seen_urls:
                            seen_urls.add(p.url)
                            products.append(p)
                else:
                    # Default: procesar con Python
                    for item in serp_data.get("organic_results", []):
                        snippet = item.get("snippet", "")
                        title = item.get("title", "")
                        price_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*€', snippet + " " + title)
                        if price_match:
                            price_str = price_match.group(1).replace(".", "").replace(",", ".")
                            try:
                                price = float(price_str)
                                if price > 10:
                                    products.append(ShoppingResult(
                                        position=len(products) + 1,
                                        title=title,
                                        price=price,
                                        store=item.get("displayed_link", "").split("/")[0],
                                        url=item.get("link", "")
                                    ))
                            except:
                                pass
                
                # Añadir similitud y tipo
                for p in products:
                    p.result_type = "Organic"
                    p.similarity = calculate_similarity(product_query, p.title)
                    products_by_type["Organic"].append(p)
                
                st.write(f"✅ {len(products)} productos con precio encontrados")
                            
            except Exception as e:
                st.error(f"❌ Error en extracción: {str(e)}")
                st.stop()
        
        # Combinar todos los productos
        all_products = []
        for type_products in products_by_type.values():
            all_products.extend(type_products)
        
        if not all_products:
            st.warning("⚠️ No se encontraron productos con precios.")
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
    # MOSTRAR RESULTADOS
    # =============================================
    st.divider()
    st.header("📊 Resultados")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    total_products = len(all_products)
    exact_matches = len([p for p in all_products if hasattr(p, 'similarity') and p.similarity >= 85])
    
    with col1:
        if analysis.your_serp_position:
            st.metric("📍 Tu posición", f"#{analysis.your_serp_position}")
        else:
            st.metric("📍 Tu posición", "No apareces")
    
    with col2:
        st.metric("💰 Ranking precio", f"#{analysis.your_price_position} de {total_products + 1}")
    
    with col3:
        st.metric("🔍 Total productos", total_products)
    
    with col4:
        st.metric("✅ Coincidencias exactas", exact_matches)
    
    # =============================================
    # TABLAS POR TIPO
    # =============================================
    
    your_domain_clean = your_domain.replace('www.', '').lower()
    
    def create_results_table(products_list, type_name):
        """Crea una tabla de resultados."""
        if not products_list:
            return None
        
        table_data = []
        for p in sorted(products_list, key=lambda x: x.price):
            similarity = getattr(p, 'similarity', calculate_similarity(product_query, p.title))
            match_label, _ = classify_match(similarity)
            price_diff = calculate_price_diff(p.price, your_price)
            
            store_clean = p.store.lower() if p.store else ""
            url_clean = p.url.lower() if p.url else ""
            is_you = your_domain_clean in store_clean or your_domain_clean in url_clean
            
            table_data.append({
                "Tienda": p.store or "Desconocida",
                "Producto": p.title[:60] + "..." if len(p.title) > 60 else p.title,
                "Precio": f"{p.price:.2f}€",
                "vs Tu precio": price_diff,
                "Match": match_label,
                "URL": p.url or "",
                "": "👈 TÚ" if is_you else ""
            })
        
        return pd.DataFrame(table_data)
    
    # Tabs para cada tipo
    tab_names = []
    tab_data = []
    
    for type_name, products_list in products_by_type.items():
        if products_list:
            tab_names.append(f"{type_name} ({len(products_list)})")
            tab_data.append((type_name, products_list))
    
    if tab_names:
        tabs = st.tabs(tab_names)
        
        for i, tab in enumerate(tabs):
            with tab:
                type_name, products_list = tab_data[i]
                df = create_results_table(products_list, type_name)
                
                if df is not None:
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "URL": st.column_config.LinkColumn("🔗 Link", display_text="Ver"),
                            "Producto": st.column_config.TextColumn("Producto", width="large"),
                        }
                    )
                    
                    csv = convert_df_to_csv(df)
                    st.download_button(
                        label=f"📥 Exportar {type_name} a CSV",
                        data=csv,
                        file_name=f"serp_{type_name.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
                    )
    
    # =============================================
    # TABLA RESUMEN GENERAL
    # =============================================
    st.subheader("📋 Resumen General")
    
    all_table_data = []
    for p in sorted(all_products, key=lambda x: x.price):
        similarity = getattr(p, 'similarity', calculate_similarity(product_query, p.title))
        match_label, _ = classify_match(similarity)
        price_diff = calculate_price_diff(p.price, your_price)
        result_type = getattr(p, 'result_type', 'Other')
        
        store_clean = p.store.lower() if p.store else ""
        url_clean = p.url.lower() if p.url else ""
        is_you = your_domain_clean in store_clean or your_domain_clean in url_clean
        
        all_table_data.append({
            "Tipo": result_type,
            "Tienda": p.store or "Desconocida",
            "Producto": p.title[:50] + "..." if len(p.title) > 50 else p.title,
            "Precio": f"{p.price:.2f}€",
            "vs Tu precio": price_diff,
            "Match": match_label,
            "URL": p.url or "",
            "": "👈 TÚ" if is_you else ""
        })
    
    # Añadir tu producto si no apareces
    if not analysis.your_serp_position:
        your_entry = {
            "Tipo": "Tu tienda",
            "Tienda": your_domain,
            "Producto": product_query,
            "Precio": f"{your_price:.2f}€",
            "vs Tu precio": "🟡 0%",
            "Match": "✅ Exacto",
            "URL": "",
            "": "👈 TÚ"
        }
        all_table_data.insert(analysis.your_price_position - 1, your_entry)
    
    df_all = pd.DataFrame(all_table_data)
    st.dataframe(
        df_all,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("🔗 Link", display_text="Ver"),
        }
    )
    
    csv_all = convert_df_to_csv(df_all)
    st.download_button(
        label="📥 Exportar TODO a CSV",
        data=csv_all,
        file_name="serp_analisis_completo.csv",
        mime="text/csv",
    )
    
    # =============================================
    # INSIGHTS
    # =============================================
    st.subheader("💡 Insights")
    
    # Filtrar productos con match alto
    exact_products = [p for p in all_products if hasattr(p, 'similarity') and p.similarity >= 60]
    
    if exact_products:
        exact_products_sorted = sorted(exact_products, key=lambda x: x.price)
        
        cheapest = exact_products_sorted[0]
        most_expensive = exact_products_sorted[-1]
        avg_price = sum(p.price for p in exact_products_sorted) / len(exact_products_sorted)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Estadísticas de precios")
            st.markdown(f"""
            **Solo productos similares (≥60% match):**
            
            | Métrica | Valor | Tienda |
            |---------|-------|--------|
            | 🟢 Más barato | **{cheapest.price:.2f}€** | {cheapest.store} |
            | 🔴 Más caro | **{most_expensive.price:.2f}€** | {most_expensive.store} |
            | 📊 Media | **{avg_price:.2f}€** | - |
            | 📈 Tu precio | **{your_price:.2f}€** | {your_domain} |
            """)
        
        with col2:
            st.markdown("### 🎯 Tu posición competitiva")
            
            diff_to_avg = your_price - avg_price
            diff_to_min = your_price - cheapest.price
            
            prices_below = len([p for p in exact_products_sorted if p.price < your_price])
            your_rank = prices_below + 1
            total_in_rank = len(exact_products_sorted) + 1
            
            pct_vs_avg = ((your_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            st.metric(
                "Tu ranking (productos similares)", 
                f"#{your_rank} de {total_in_rank}",
                delta=f"{pct_vs_avg:+.1f}% vs media"
            )
            
            if diff_to_avg < 0:
                st.success(f"✅ Estás **{abs(diff_to_avg):.2f}€ por debajo** de la media")
            elif diff_to_avg > 0:
                st.warning(f"⚠️ Estás **{diff_to_avg:.2f}€ por encima** de la media")
            else:
                st.info("🟡 Estás exactamente en la media")
            
            if your_rank == 1:
                st.success("🏆 ¡Tienes el mejor precio entre productos similares!")
            elif your_rank <= 3:
                st.info(f"👍 Estás en el top 3. Para ser #1, baja **{diff_to_min:.2f}€**")
            else:
                st.warning(f"💡 Para ser el más barato, deberías bajar **{diff_to_min:.2f}€**")
    
    else:
        st.info("No hay suficientes productos similares (≥60% match) para generar insights detallados.")
        
        if all_products:
            all_sorted = sorted(all_products, key=lambda x: x.price)
            cheapest = all_sorted[0]
            most_expensive = all_sorted[-1]
            avg_price = sum(p.price for p in all_sorted) / len(all_sorted)
            
            st.markdown(f"""
            **Estadísticas generales (todos los productos):**
            - 🟢 Más barato: **{cheapest.price:.2f}€** ({cheapest.store})
            - 🔴 Más caro: **{most_expensive.price:.2f}€** ({most_expensive.store})
            - 📊 Media: **{avg_price:.2f}€**
            """)

# Footer
st.divider()
st.caption("🔍 Datos de Google.es • [Extensión Chrome](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)")
