"""SERP Price Checker - Aplicación principal."""

import streamlit as st
import pandas as pd
import logging
from io import BytesIO

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Imports internos
from src.core import (
    Product, PriceAnalysis, AnalysisConfig,
    MatchLevel, analyze_prices,
    calculate_text_similarity, format_match_level,
    calculate_token_match, cluster_by_brand
)
from src.data import (
    parse_extension_csv, group_products_by_type,
    get_price_distribution
)

# Configuración de página
st.set_page_config(
    page_title="SERP Price Checker v4",
    page_icon="🔍",
    layout="wide"
)

# CSS personalizado
st.markdown("""
<style>
    .recommendation-high { background-color: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 5px 0; }
    .recommendation-medium { background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 10px; margin: 5px 0; }
    .recommendation-low { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 10px; margin: 5px 0; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }
    .offer-badge { background-color: #4caf50; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

# Título
st.title("🔍 SERP Price Checker v4")
st.markdown("Análisis inteligente de precios en **Google España** 🇪🇸")


# =============================================
# FUNCIONES AUXILIARES
# =============================================

def format_price(price: float, original: float = None) -> str:
    """Formatea precio con oferta si aplica."""
    if original and original > price:
        return f"~~{original:.2f}€~~ **{price:.2f}€**"
    return f"{price:.2f}€"


def format_price_diff(diff_pct: float, diff_abs: float) -> str:
    """Formatea diferencia de precio."""
    if diff_pct > 0:
        return f"🔴 +{diff_abs:.0f}€ (+{diff_pct:.1f}%)"
    elif diff_pct < 0:
        return f"🟢 {diff_abs:.0f}€ ({diff_pct:.1f}%)"
    else:
        return "🟡 Igual"


def format_match_level(level: MatchLevel, score: float) -> str:
    """Formatea nivel de coincidencia."""
    if level == MatchLevel.EXACT:
        return "✅ Exacto"
    elif level == MatchLevel.VERY_SIMILAR:
        return f"🔷 Muy similar ({score*100:.0f}%)"
    elif level == MatchLevel.SIMILAR:
        return f"🔶 Similar ({score*100:.0f}%)"
    elif level == MatchLevel.RELATED:
        return f"🟡 Relacionado ({score*100:.0f}%)"
    else:
        return f"⚪ Diferente ({score*100:.0f}%)"


def export_to_excel(df: pd.DataFrame) -> bytes:
    """Exporta DataFrame a Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Análisis')
    return output.getvalue()


def _render_your_products_table(products, use_agent: bool, api_key: str, provider: str):
    """Renderiza tabla de productos con o sin análisis de agente."""
    your_data = []
    entities_data = []
    
    for p in products:
        row = {
            "Tienda": p.store,
            "Producto": p.title[:60] + "..." if len(p.title) > 60 else p.title,
            "Precio": f"{p.price:.2f}€" if p.has_price else "-",
            "Match": format_match_level(p.match_level, p.match_score) if hasattr(p, 'match_level') and p.match_level else "-",
            "URL": p.url
        }
        your_data.append(row)
    
    df_your = pd.DataFrame(your_data)
    st.dataframe(df_your, use_container_width=True, hide_index=True,
                column_config={"URL": st.column_config.LinkColumn("🔗", display_text="Ver")})
    
    # Análisis con agente IA
    if use_agent and api_key:
        with st.expander("🤖 Análisis de entidades con IA", expanded=False):
            if st.button("Analizar entidades", key=f"analyze_{id(products)}"):
                try:
                    from src.services import extract_entities_with_llm
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    entities_results = []
                    for i, p in enumerate(products):
                        status_text.text(f"Analizando {i+1}/{len(products)}: {p.title[:40]}...")
                        progress_bar.progress((i + 1) / len(products))
                        
                        entities = extract_entities_with_llm(
                            p.title,
                            p.price if p.has_price else None,
                            api_key,
                            provider
                        )
                        
                        entity_row = {"Producto": p.title[:40] + "..."}
                        entity_dict = entities.to_dict()
                        entity_row.update(entity_dict)
                        
                        # Añadir info de precio si es diferente
                        if entities.price_detected and entities.price_confidence != "none":
                            confidence_icon = {"high": "✅", "medium": "⚠️", "low": "❓"}.get(entities.price_confidence, "")
                            if p.has_price and abs(entities.price_detected - p.price) > 1:
                                entity_row["Precio IA"] = f"{confidence_icon} {entities.price_detected:.2f}€ (detectado: {p.price:.2f}€)"
                            else:
                                entity_row["Precio IA"] = f"{confidence_icon} {entities.price_detected:.2f}€"
                        elif not p.has_price:
                            entity_row["Precio IA"] = "❓ No detectado"
                        
                        entities_results.append(entity_row)
                    
                    status_text.text("✅ Análisis completado")
                    progress_bar.empty()
                    
                    if entities_results:
                        df_entities = pd.DataFrame(entities_results)
                        st.dataframe(df_entities, use_container_width=True, hide_index=True)
                        
                except ImportError:
                    st.error("❌ Instala las dependencias del agente: `pip install anthropic openai`")
                except Exception as e:
                    st.error(f"❌ Error en análisis: {str(e)}")


# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Tu tienda (primero)
    st.markdown("### 🏪 Tu producto")
    your_domain = st.text_input("Tu dominio", placeholder="mitienda.es", 
                                 help="Ej: pccomponentes.com, mediamarkt.es")
    your_url = st.text_input("🔗 URL de tu producto (opcional)", placeholder="https://...",
                              help="Si la proporcionas, identificamos exactamente tu producto")
    your_price = st.number_input("💰 Tu precio (€)", min_value=0.0, step=0.01, format="%.2f",
                                  help="Precio actual de tu producto")
    
    st.divider()
    
    # Opciones de análisis
    st.markdown("### 📊 Opciones")
    show_all_products = st.checkbox("Mostrar todos los productos", value=False,
                                     help="Incluye Organic/Ads sin precio")
    
    st.divider()
    
    # Agente LLM
    st.markdown("### 🤖 Agente IA (opcional)")
    use_agent = st.checkbox("Activar análisis con IA", value=False,
                            help="Usa IA para extraer entidades de los productos")
    
    llm_provider = None
    llm_api_key = None
    
    if use_agent:
        llm_provider = st.selectbox("Proveedor", ["anthropic", "openai"],
                                     help="Selecciona el proveedor de IA")
        llm_api_key = st.text_input("API Key", type="password",
                                     help="Tu API key del proveedor seleccionado")
        
        if not llm_api_key:
            st.warning("⚠️ Introduce tu API key para usar el agente")
        else:
            st.success("✅ API key configurada")


# =============================================
# FORMULARIO PRINCIPAL
# =============================================
st.markdown("---")

product_query = st.text_input("🔎 Producto a analizar", placeholder="Portátil MSI Cyborg 15")

# Upload CSV
st.markdown("### 📁 Datos de Google Shopping")

col1, col2 = st.columns([3, 1])
with col1:
    st.info("Sube el CSV exportado de la extensión **Google Rank Checker**")
with col2:
    st.link_button(
        "📥 Extensión",
        "https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es",
        use_container_width=True
    )

uploaded_file = st.file_uploader("Selecciona CSV", type=["csv", "txt"])


# =============================================
# ANÁLISIS
# =============================================
if st.button("🚀 Analizar", type="primary", use_container_width=True):
    
    # Validaciones
    if not product_query:
        st.error("❌ Introduce el producto")
        st.stop()
    if not your_domain:
        st.error("❌ Introduce tu dominio")
        st.stop()
    if your_price <= 0:
        st.error("❌ Introduce tu precio")
        st.stop()
    if not uploaded_file:
        st.error("❌ Sube el archivo CSV")
        st.stop()
    
    # Procesar
    with st.status("Analizando...", expanded=True) as status:
        
        # 1. Parsear CSV
        st.write("📁 Parseando CSV...")
        csv_content = uploaded_file.read().decode('utf-8')
        products = parse_extension_csv(csv_content)
        st.write(f"✅ {len(products)} productos encontrados")
        
        # 2. Marcar productos de tu tienda
        your_domain_clean = your_domain.lower().replace('www.', '')
        for p in products:
            if your_domain_clean in (p.store or '').lower() or your_domain_clean in (p.url or '').lower():
                p.is_your_product = True
        
        # 3. Calcular similitud de texto (legacy)
        for p in products:
            p.similarity_text = calculate_text_similarity(product_query, p.title)
        
        # 4. Análisis completo
        st.write("📊 Generando análisis...")
        config = AnalysisConfig(
            your_domain=your_domain,
            your_price=your_price,
            your_product_url=your_url if your_url else None,
            product_query=product_query,
        )
        
        analysis = analyze_prices(products, config)
        
        status.update(label="✅ Análisis completado", state="complete")
    
    # =============================================
    # RESULTADOS
    # =============================================
    st.divider()
    
    # Lista de productos con precio para usar en gráficos
    products_with_price = [p for p in products if p.has_price]
    
    # === MÉTRICAS PRINCIPALES ===
    st.header("📊 Resumen")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pos = analysis.your_serp_position or "No apareces"
        st.metric("📍 Posición SERP", pos)
    
    with col2:
        # Si ya apareces en resultados, el denominador es total_with_price
        # Si no apareces, el denominador es total_with_price + 1 (tú serías uno más)
        total_ranked = analysis.total_with_price if analysis.your_serp_position else analysis.total_with_price + 1
        st.metric("💰 Ranking Precio", f"#{analysis.your_price_rank} de {total_ranked}")
    
    with col3:
        st.metric("🏪 Competidores", analysis.total_stores)
    
    with col4:
        exact = len(analysis.exact_matches)
        st.metric("🎯 Productos equivalentes", exact)
    
    # === RECOMENDACIONES ===
    if analysis.recommendations:
        st.header("💡 Recomendaciones")
        
        for rec in analysis.recommendations:
            css_class = f"recommendation-{rec.priority}"
            icon = "🔴" if rec.priority == "high" else "🟠" if rec.priority == "medium" else "🔵"
            
            with st.expander(f"{icon} {rec.title}", expanded=(rec.priority == "high")):
                st.markdown(f"**{rec.description}**")
                st.markdown(f"👉 **Acción:** {rec.action}")
                st.markdown(f"📈 **Impacto:** {rec.impact}")
    
    # === TUS PRODUCTOS ===
    if analysis.your_store_products:
        st.header(f"🏪 Tus productos en esta búsqueda ({len(analysis.your_store_products)})")
        
        # Agrupar por tipo
        your_products_by_type = {}
        for p in analysis.your_store_products:
            ptype = p.result_type or "Otros"
            if ptype not in your_products_by_type:
                your_products_by_type[ptype] = []
            your_products_by_type[ptype].append(p)
        
        # Crear pestañas
        type_names = list(your_products_by_type.keys())
        type_names_display = [f"{t} ({len(your_products_by_type[t])})" for t in type_names]
        
        if len(type_names) > 1:
            your_tabs = st.tabs(type_names_display)
            
            for i, tab in enumerate(your_tabs):
                with tab:
                    type_products = your_products_by_type[type_names[i]]
                    _render_your_products_table(type_products, use_agent, llm_api_key, llm_provider)
        else:
            # Solo un tipo, mostrar sin pestañas
            _render_your_products_table(analysis.your_store_products, use_agent, llm_api_key, llm_provider)
    
    # === GRÁFICO DE PRECIOS ===
    st.header("📈 Distribución de precios")
    
    distribution = get_price_distribution(products_with_price, bins=8)
    if distribution:
        chart_data = pd.DataFrame(distribution)
        
        # Marcar dónde está tu precio
        your_bin = None
        for i, d in enumerate(distribution):
            if d['low'] <= your_price < d['high']:
                your_bin = i
                break
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.bar_chart(chart_data.set_index('range')['count'])
        
        with col2:
            st.markdown(f"""
            **Tu precio:** {your_price:.2f}€
            
            **Rango de mercado:**
            - Mínimo: {analysis.min_price:.2f}€
            - Máximo: {analysis.max_price:.2f}€
            - Media: {analysis.avg_price:.2f}€
            - Mediana: {analysis.median_price:.2f}€
            """)
    
    # === CLUSTERS ===
    if analysis.clusters:
        st.header("🗂️ Productos agrupados por categoría")
        
        for cluster in analysis.clusters[:5]:  # Top 5 clusters
            is_your_cluster = analysis.your_cluster and cluster.key == analysis.your_cluster.key
            
            title = f"{'⭐ ' if is_your_cluster else ''}{cluster.name} ({len(cluster.products)} productos)"
            
            with st.expander(title, expanded=is_your_cluster):
                cluster_data = []
                for p in sorted(cluster.products, key=lambda x: x.price):
                    cluster_data.append({
                        "": "👈 TÚ" if p.is_your_product else "",
                        "Tienda": p.store,
                        "Producto": p.title[:45] + "..." if len(p.title) > 45 else p.title,
                        "Precio": f"{p.price:.2f}€",
                        "Dif. €": f"{p.price_diff_abs:+.0f}€" if p.price_diff_abs else "-",
                        "Dif. %": f"{p.price_diff_pct:+.1f}%" if p.price_diff_pct else "-",
                        "🔗": p.url
                    })
                
                df_cluster = pd.DataFrame(cluster_data)
                st.dataframe(df_cluster, use_container_width=True, hide_index=True,
                            column_config={"🔗": st.column_config.LinkColumn("🔗", display_text="Ver")})
    
    # === TABLA POR TIPO ===
    st.header("📋 Resultados por tipo")
    
    by_type = group_products_by_type(products)
    
    tab_names = []
    tab_data = []
    for type_name, type_products in by_type.items():
        if type_products or show_all_products:
            count = len(type_products)
            tab_names.append(f"{type_name} ({count})")
            tab_data.append((type_name, type_products))
    
    if tab_names:
        tabs = st.tabs(tab_names)
        
        for i, tab in enumerate(tabs):
            with tab:
                type_name, type_products = tab_data[i]
                
                if not type_products:
                    st.info("No hay resultados de este tipo")
                    continue
                
                # Separar con y sin precio
                with_price = sorted([p for p in type_products if p.has_price], key=lambda x: x.price)
                without_price = [p for p in type_products if not p.has_price]
                
                table_data = []
                
                for p in with_price:
                    match_str = format_match_level(p.match_level, p.match_score) if hasattr(p, 'match_level') else f"{p.similarity_text:.0f}%"
                    
                    row = {
                        "": "👈 TÚ" if p.is_your_product else "",
                        "Tienda": p.store,
                        "Producto": p.title[:50] + "..." if len(p.title) > 50 else p.title,
                        "Precio": format_price(p.price, p.original_price),
                        "Dif. €": f"{p.price_diff_abs:+.0f}€" if p.price_diff_abs else "-",
                        "Dif. %": f"{p.price_diff_pct:+.1f}%" if p.price_diff_pct else "-",
                        "Match": match_str,
                        "🔗": p.url
                    }
                    
                    if p.is_offer:
                        row["Precio"] = f"🏷️ {row['Precio']}"
                    
                    table_data.append(row)
                
                # Sin precio
                for p in without_price:
                    table_data.append({
                        "": "👈 TÚ" if p.is_your_product else "",
                        "Tienda": p.store,
                        "Producto": p.title[:50] + "..." if len(p.title) > 50 else p.title,
                        "Precio": "-",
                        "Dif. €": "-",
                        "Dif. %": "-",
                        "Match": "-",
                        "🔗": p.url
                    })
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True, hide_index=True,
                                column_config={"🔗": st.column_config.LinkColumn("🔗", display_text="Ver")})
                    
                    # Exportar
                    col1, col2 = st.columns(2)
                    with col1:
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(f"📥 CSV", csv, f"serp_{type_name.lower().replace(' ', '_')}.csv", "text/csv")
                    with col2:
                        xlsx = export_to_excel(df)
                        st.download_button(f"📥 Excel", xlsx, f"serp_{type_name.lower().replace(' ', '_')}.xlsx")
    
    # === TABLA COMPLETA ===
    st.header("📋 Análisis completo")
    
    all_data = []
    
    # Productos con precio ordenados
    sorted_products = sorted([p for p in products if p.has_price], key=lambda x: x.price)
    
    # Insertar tu producto si no apareces
    your_inserted = False
    insert_position = 0
    
    for i, p in enumerate(sorted_products):
        if not your_inserted and p.price >= your_price:
            insert_position = i
            your_inserted = True
    
    if not your_inserted:
        insert_position = len(sorted_products)
    
    for i, p in enumerate(sorted_products):
        # Insertar tu producto
        if i == insert_position and not analysis.your_serp_position:
            all_data.append({
                "Pos": i + 1,
                "": "👈 TÚ",
                "Tipo": "Tu tienda",
                "Tienda": your_domain,
                "Producto": product_query,
                "Precio": f"{your_price:.2f}€",
                "Dif. €": "0€",
                "Dif. %": "0%",
                "Match": "✅ Referencia",
                "URL": ""
            })
        
        match_str = format_match_level(p.match_level, p.match_score) if hasattr(p, 'match_level') else "-"
        
        price_str = f"{p.price:.2f}€"
        if p.is_offer and p.original_price:
            price_str = f"🏷️ ~~{p.original_price:.2f}€~~ {p.price:.2f}€"
        
        all_data.append({
            "Pos": len(all_data) + 1,
            "": "👈 TÚ" if p.is_your_product else "",
            "Tipo": p.result_type,
            "Tienda": p.store,
            "Producto": p.title[:40] + "..." if len(p.title) > 40 else p.title,
            "Precio": price_str,
            "Dif. €": f"{p.price_diff_abs:+.0f}€" if p.price_diff_abs else "-",
            "Dif. %": f"{p.price_diff_pct:+.1f}%" if p.price_diff_pct else "-",
            "Match": match_str,
            "URL": p.url
        })
    
    df_all = pd.DataFrame(all_data)
    st.dataframe(df_all, use_container_width=True, hide_index=True,
                column_config={"URL": st.column_config.LinkColumn("🔗", display_text="Ver")})
    
    # Exportar todo
    col1, col2 = st.columns(2)
    with col1:
        csv_all = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV completo", csv_all, "analisis_completo.csv", "text/csv")
    with col2:
        xlsx_all = export_to_excel(df_all)
        st.download_button("📥 Exportar Excel completo", xlsx_all, "analisis_completo.xlsx")


# Footer
st.divider()
st.caption("🔍 SERP Price Checker v4 • [Extensión Chrome](https://chromewebstore.google.com/detail/google-rank-checkerkeywor/hcghkofiggmpkedhjkpnpmaimfbbgfdo?hl=es)")
