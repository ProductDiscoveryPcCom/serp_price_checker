import streamlit as st
import requests
from src import (
    scrape_google_shopping,
    extract_shopping_with_claude,
    extract_shopping_with_openai,
    build_analysis,
    preprocess_html,
)

# Configuración de página
st.set_page_config(
    page_title="SERP Price Checker",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 SERP Price Checker")
st.markdown("Analiza tu competitividad de precios en **Google Shopping** (España)")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # API Keys desde secrets o input manual
    zenrows_key = st.text_input(
        "ZenRows API Key",
        value=st.secrets.get("ZENROWS_API_KEY", ""),
        type="password"
    )
    
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
    
    st.divider()
    st.markdown("### Tu tienda")
    your_domain = st.text_input(
        "Tu dominio/nombre de tienda",
        placeholder="mitienda.es"
    )
    
    st.divider()
    st.markdown("### Avanzado")
    wait_time = st.slider(
        "Tiempo espera JS (ms)",
        min_value=1000,
        max_value=15000,
        value=5000,
        step=1000,
        help="Tiempo de espera para que cargue el JavaScript de Google Shopping"
    )

# Formulario principal
col1, col2 = st.columns([3, 1])

with col1:
    product_query = st.text_input(
        "🔎 Producto a buscar",
        placeholder="Samsung Galaxy S24 Ultra 256GB Negro"
    )

with col2:
    your_price = st.number_input(
        "💰 Tu precio (€)",
        min_value=0.0,
        step=0.01,
        format="%.2f"
    )

# Botón de análisis
if st.button("🚀 Analizar competencia", type="primary", use_container_width=True):
    
    # Validaciones
    if not zenrows_key:
        st.error("❌ Falta la API Key de ZenRows")
        st.stop()
    if not llm_key:
        st.error(f"❌ Falta la API Key de {llm_provider}")
        st.stop()
    if not product_query:
        st.error("❌ Introduce un producto a buscar")
        st.stop()
    if not your_domain:
        st.error("❌ Introduce tu dominio")
        st.stop()
    if your_price <= 0:
        st.error("❌ Introduce tu precio")
        st.stop()
    
    # Proceso de análisis
    with st.status("Analizando Google Shopping...", expanded=True) as status:
        
        # Paso 1: Scraping Google Shopping
        st.write("🛒 Obteniendo resultados de Google Shopping España...")
        try:
            html = scrape_google_shopping(
                query=product_query,
                zenrows_api_key=zenrows_key,
                wait_ms=wait_time
            )
            html_size = len(html)
            st.write(f"✅ HTML obtenido ({html_size:,} caracteres)")
            
            # Preprocesar para diagnóstico
            html_stats = preprocess_html(html)
            
            # Debug: mostrar diagnóstico
            with st.expander("🔍 Debug: Diagnóstico del HTML"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Detección de precios:**")
                    if html_stats["has_euro_symbol"]:
                        st.success("✅ Símbolo € encontrado")
                    else:
                        st.error("❌ No se encontró símbolo €")
                    
                    if html_stats["price_patterns_found"]:
                        st.success(f"✅ {len(html_stats['price_patterns_found'])} precios detectados")
                        st.code(", ".join(html_stats["price_patterns_found"][:5]))
                    else:
                        st.error("❌ No se detectaron patrones de precio")
                
                with col2:
                    st.markdown("**Tiendas detectadas:**")
                    if html_stats["potential_stores"]:
                        st.success(f"✅ {', '.join(html_stats['potential_stores'])}")
                    else:
                        st.warning("⚠️ No se detectaron tiendas conocidas")
                
                st.markdown("**Preview HTML (primeros 3000 chars):**")
                st.code(html[:3000] + "..." if len(html) > 3000 else html, language="html")
                        
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ Error HTTP de ZenRows: {e.response.status_code}")
            st.code(e.response.text[:500] if hasattr(e, 'response') else str(e))
            st.stop()
        except Exception as e:
            st.error(f"❌ Error en scraping: {str(e)}")
            st.stop()
        
        if not html or len(html) < 1000:
            st.warning("⚠️ HTML demasiado corto, posible bloqueo")
            st.stop()
        
        # Verificar si hay precios en el HTML
        if not html_stats["has_euro_symbol"] and not html_stats["price_patterns_found"]:
            st.error("❌ No se detectaron precios en el HTML. Posibles causas:")
            st.markdown("""
            - Google puede estar bloqueando el scraping
            - La página requiere más tiempo de carga JS
            - El producto no tiene resultados en Google Shopping
            """)
            st.stop()
        
        # Paso 2: Extracción con LLM
        st.write("🤖 Extrayendo productos con IA...")
        try:
            if llm_provider == "Claude (Anthropic)":
                shopping_results = extract_shopping_with_claude(
                    query=product_query,
                    html=html,
                    api_key=llm_key
                )
            else:
                shopping_results = extract_shopping_with_openai(
                    query=product_query,
                    html=html,
                    api_key=llm_key
                )
            st.write(f"✅ {len(shopping_results)} productos extraídos")
            
            # Debug: mostrar productos extraídos
            if shopping_results:
                with st.expander("🔍 Debug: Productos extraídos"):
                    for p in shopping_results[:5]:
                        st.json({
                            "position": p.position,
                            "title": p.title[:50] + "..." if len(p.title) > 50 else p.title,
                            "price": p.price,
                            "store": p.store
                        })
                        
        except Exception as e:
            st.error(f"❌ Error en extracción LLM: {str(e)}")
            st.stop()
        
        if not shopping_results:
            st.warning("⚠️ No se encontraron productos en Google Shopping")
            st.stop()
        
        # Paso 3: Construir análisis
        st.write("📊 Generando análisis...")
        analysis = build_analysis(
            query=product_query,
            your_domain=your_domain,
            your_price=your_price,
            shopping_results=shopping_results
        )
        
        status.update(label="✅ Análisis completado", state="complete")
    
    # Mostrar resultados
    st.divider()
    st.header("📊 Resultados")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if analysis.your_serp_position:
            st.metric("🛒 Tu posición Shopping", f"#{analysis.your_serp_position}")
        else:
            st.metric("🛒 Tu posición Shopping", "No apareces", delta="❌", delta_color="off")
    
    with col2:
        total_with_price = len(analysis.competitors)
        st.metric(
            "💰 Tu posición precio",
            f"#{analysis.your_price_position} de {total_with_price + 1}"
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
        st.metric("🔍 Productos encontrados", analysis.total_organic_results)
    
    # Tabla de competidores
    st.subheader("🏆 Ranking por precio en Google Shopping")
    
    if analysis.competitors:
        # Preparar datos para la tabla
        table_data = []
        
        for i, comp in enumerate(analysis.competitors, 1):
            store_clean = comp.store.lower() if comp.store else ""
            your_domain_clean = your_domain.replace('www.', '').lower()
            is_you = your_domain_clean in store_clean or store_clean in your_domain_clean
            
            table_data.append({
                "Pos.": i,
                "Tienda": comp.store or "Desconocida",
                "Producto": comp.title[:60] + "..." if len(comp.title) > 60 else comp.title,
                "Precio": f"{comp.price:.2f}€" if comp.price else "N/A",
                "": "👈 TÚ" if is_you else ""
            })
        
        # Añadir tu posición si no apareces en Shopping
        if not analysis.your_serp_position:
            your_entry = {
                "Pos.": analysis.your_price_position,
                "Tienda": your_domain,
                "Producto": "(Tu producto)",
                "Precio": f"{your_price:.2f}€",
                "": "👈 TÚ"
            }
            table_data.insert(analysis.your_price_position - 1, your_entry)
            # Reajustar posiciones
            for i, row in enumerate(table_data, 1):
                row["Pos."] = i
        
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True
        )
        
        # Insights
        st.subheader("💡 Insights")
        
        cheapest = analysis.competitors[0]
        most_expensive = analysis.competitors[-1]
        avg_price = sum(c.price for c in analysis.competitors if c.price) / len(analysis.competitors)
        
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
                st.info(f"👍 Estás en el top 3 por precio")
            else:
                st.warning(f"💡 Para ser el más barato, baja **{diff_to_min:.2f}€**")
    else:
        st.info("No se encontraron competidores con precios en Google Shopping")

# Footer
st.divider()
st.caption("🛒 Datos extraídos de Google Shopping España mediante ZenRows + IA")
