#!/usr/bin/env python3
"""
Calculadora de Precios para Marketplaces — México 2026
Mercado Libre y Amazon México con comisiones reales 2026
Sincronización con Shopify morekashop1 para obtener costos
"""

import streamlit as st
import pandas as pd
import requests
import time
import io
from datetime import datetime

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Marketplace Pricing Calculator MX",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS PERSONALIZADO
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
    }
    .metric-card-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
    }
    .metric-card-orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
    }
    .metric-card-blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 1rem;
        color: #856404;
    }
    .danger-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        padding: 1rem;
        color: #721c24;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        color: #155724;
    }
    .fee-breakdown {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    .profit-positive { color: #11998e; font-weight: 700; }
    .profit-negative { color: #f5576c; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# COMISIONES MERCADO LIBRE MÉXICO 2026
# ============================================================
ML_CATEGORIES = {
    "Celulares y Telefonía": {"classic": 0.10, "premium": 0.145},
    "Computación": {"classic": 0.10, "premium": 0.145},
    "Electrónica, Audio y Video": {"classic": 0.10, "premium": 0.125},
    "Cámaras y Accesorios": {"classic": 0.10, "premium": 0.145},
    "Instrumentos Musicales": {"classic": 0.10, "premium": 0.145},
    "Consolas y Videojuegos": {"classic": 0.10, "premium": 0.145},
    "Agro": {"classic": 0.10, "premium": 0.145},
    "Alimentos y Bebidas": {"classic": 0.10, "premium": 0.145},
    "Antigüedades y Colecciones": {"classic": 0.10, "premium": 0.145},
    "Accesorios para Vehículos": {"classic": 0.12, "premium": 0.165},
    "Industrias y Oficinas": {"classic": 0.12, "premium": 0.165},
    "Herramientas": {"classic": 0.135, "premium": 0.18},
    "Belleza y Cuidado Personal": {"classic": 0.14, "premium": 0.185},
    "Salud y Equipamiento Médico": {"classic": 0.14, "premium": 0.185},
    "Electrodomésticos": {"classic": 0.15, "premium": 0.195},
    "Deportes y Fitness": {"classic": 0.15, "premium": 0.195},
    "Hogar, Muebles y Jardín": {"classic": 0.15, "premium": 0.195},
    "Juegos y Juguetes": {"classic": 0.15, "premium": 0.195},
    "Joyas y Relojes": {"classic": 0.15, "premium": 0.195},
    "Libros, Revistas y Cómics": {"classic": 0.15, "premium": 0.195},
    "Mascotas": {"classic": 0.15, "premium": 0.195},
    "Música, Películas y Series": {"classic": 0.15, "premium": 0.195},
    "Recuerdos, Cotillón y Fiestas": {"classic": 0.15, "premium": 0.195},
    "Ropa, Bolsas y Calzado": {"classic": 0.15, "premium": 0.195},  # Simplificado
    "Arte, Papelería y Mercería": {"classic": 0.15, "premium": 0.195},
    "Bebés": {"classic": 0.15, "premium": 0.195},
    "Construcción": {"classic": 0.15, "premium": 0.195},
    "Custom": {"classic": 0.15, "premium": 0.195},
}

# ============================================================
# COMISIONES AMAZON MÉXICO 2026
# ============================================================
AMAZON_CATEGORIES = {
    "Electrónica de Consumo": 0.08,
    "Computadoras": 0.08,
    "Cámaras y Fotografía": 0.08,
    "Accesorios Electrónicos": 0.15,  # Hasta $100, 8% por encima - simplificado
    "Belleza (≤$10)": 0.08,
    "Belleza (>$10)": 0.15,
    "Salud y Cuidado Personal (≤$10)": 0.08,
    "Salud y Cuidado Personal (>$10)": 0.15,
    "Hogar y Cocina": 0.15,
    "Juguetes y Juegos": 0.15,
    "Deportes y Aire Libre": 0.15,
    "Herramientas y Mejora del Hogar": 0.15,
    "Césped y Jardín": 0.15,
    "Productos para Mascotas": 0.15,
    "Automotriz y Deportes de Motor": 0.12,
    "Instrumentos Musicales": 0.15,
    "Libros, Música, DVD, Video": 0.15,
    "Ropa y Accesorios": 0.15,  # 5-17% escalonado - simplificado
    "Joyas y Relojes": 0.20,  # 20% hasta $250, 5% por encima - simplificado
    "Accesorios para dispositivos Amazon": 0.45,
    "Todo lo demás": 0.15,
    "Custom": 0.15,
}

# ============================================================
# FUNCIONES DE CÁLCULO — MERCADO LIBRE MÉXICO
# ============================================================
def get_ml_fixed_fee(price, listing_type="classic"):
    """Costo fijo adicional para publicación Clásica (solo si precio < $299)"""
    if listing_type != "classic":
        return 0
    if price < 99:
        return 25
    elif price < 149:
        return 30
    elif price < 299:
        return 37
    return 0

def calculate_ml_fees(price, category_name, listing_type="classic", has_rfc=True):
    """Calcula todas las comisiones de Mercado Libre México para un precio dado."""
    cat = ML_CATEGORIES.get(category_name, ML_CATEGORIES["Custom"])
    commission_rate = cat[listing_type]
    
    # Comisión por venta
    commission = price * commission_rate
    
    # Costo fijo adicional (solo Clásica, precio < $299)
    fixed_fee = get_ml_fixed_fee(price, listing_type)
    
    # Base gravable (precio sin IVA - asumiendo precio con IVA incluido)
    base_gravable = price / 1.16
    
    # IVA retenido
    if has_rfc:
        iva_ret = base_gravable * 0.08  # 8% sobre base gravable (50% del IVA)
    else:
        iva_ret = base_gravable * 0.16  # 16% completo sin RFC
    
    # ISR retenido
    if has_rfc:
        isr_ret = base_gravable * 0.025  # 2.5% desde 2026
    else:
        isr_ret = price * 0.20  # 20% sobre precio total sin RFC
    
    total_fees = commission + fixed_fee + iva_ret + isr_ret
    
    return {
        "commission_rate": commission_rate,
        "commission": commission,
        "fixed_fee": fixed_fee,
        "base_gravable": base_gravable,
        "iva_ret": iva_ret,
        "isr_ret": isr_ret,
        "total_fees": total_fees,
        "net_received": price - total_fees,
    }

def calculate_ml_price_from_cost(cost, target_margin, category_name, listing_type="classic", has_rfc=True, shipping_cost=0):
    """Calcula el precio de venta necesario para obtener el margen deseado en ML."""
    cat = ML_CATEGORIES.get(category_name, ML_CATEGORIES["Custom"])
    commission_rate = cat[listing_type]
    
    # Tarifa total aproximada (comisión + IVA + ISR)
    if has_rfc:
        # Base gravable = price / 1.16
        # IVA = 8% * base = 8% * price/1.16 = 6.90% * price
        # ISR = 2.5% * base = 2.5% * price/1.16 = 2.16% * price
        # Total impuestos = 9.06% * price
        tax_rate = (0.08 + 0.025) / 1.16
        # Fixed fee es tricky - estimate for products > $299
        fixed_fee = 0
    else:
        # Sin RFC: IVA 16% sobre base = 13.79%, ISR 20% sobre total = 20%
        tax_rate = (0.16 / 1.16) + 0.20
        fixed_fee = 0
    
    total_fee_rate = commission_rate + tax_rate
    
    # Precio = (Costo + Envío + FixedFee) / (1 - margen - tarifa_total)
    denominator = 1 - target_margin - total_fee_rate
    if denominator <= 0:
        return None
    
    price = (cost + shipping_cost + fixed_fee) / denominator
    
    # Iterar para ajustar fixed fee si el precio cae < $299
    for _ in range(5):
        fixed_fee = get_ml_fixed_fee(price, listing_type)
        price = (cost + shipping_cost + fixed_fee) / denominator
    
    return round(price, 2)

def calculate_ml_with_discount(cost, base_price, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0):
    """Calcula métricas cuando se aplica un descuento al precio base."""
    discounted_price = round(base_price * (1 - discount_pct), 2)
    fees = calculate_ml_fees(discounted_price, category_name, listing_type, has_rfc)
    
    total_cost = cost + shipping_cost
    profit = discounted_price - total_cost - fees["total_fees"]
    profit_margin = (profit / discounted_price) * 100 if discounted_price > 0 else 0
    
    return {
        "base_price": base_price,
        "discounted_price": discounted_price,
        "discount_amount": round(base_price - discounted_price, 2),
        "discount_pct": discount_pct * 100,
        "fees": fees,
        "profit": round(profit, 2),
        "profit_margin": round(profit_margin, 2),
        "profit_pct_cost": round((profit / cost) * 100, 2) if cost > 0 else 0,
        "total_cost": total_cost,
    }

# ============================================================
# FUNCIONES DE CÁLCULO — AMAZON MÉXICO
# ============================================================
def calculate_amazon_fees(price, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula todas las comisiones de Amazon México para un precio dado."""
    referral_rate = AMAZON_CATEGORIES.get(category_name, 0.15)
    
    # Referral fee
    referral = price * referral_rate
    
    # Tarifa mínima por artículo (aproximada)
    min_fee = 5.0 if referral < 5 else 0
    if min_fee > 0:
        referral = max(referral, min_fee)
    
    # Plan profesional (prorrateado por unidad - aproximado)
    plan_fee = 20.0 if plan_professional else 0  # $600/mes ÷ 30 unidades = $20/unidad aprox
    
    # FBA o FBM shipping
    fba = fba_fee if fba_fee else 0
    shipping = shipping_cost if not fba_fee else 0
    
    total_fees = referral + plan_fee + fba + shipping
    
    return {
        "referral_rate": referral_rate,
        "referral": referral,
        "min_fee": min_fee,
        "plan_fee": plan_fee,
        "fba": fba,
        "shipping": shipping,
        "total_fees": total_fees,
        "net_received": price - total_fees,
    }

def calculate_amazon_price_from_cost(cost, target_margin, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula el precio de venta necesario para obtener el margen deseado en Amazon."""
    referral_rate = AMAZON_CATEGORIES.get(category_name, 0.15)
    
    # Plan fee prorrateado
    plan_fee = 20.0 if plan_professional else 0
    
    # FBA o FBM
    fba = fba_fee if fba_fee else 0
    ship = shipping_cost if not fba_fee else 0
    
    fixed_fees = plan_fee + fba + ship
    
    # Precio = (Costo + FixedFees) / (1 - margen - referral_rate)
    denominator = 1 - target_margin - referral_rate
    if denominator <= 0:
        return None
    price = (cost + fixed_fees) / denominator
    
    return round(price, 2)

def calculate_amazon_with_discount(cost, base_price, discount_pct, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula métricas cuando se aplica un descuento al precio base en Amazon."""
    discounted_price = round(base_price * (1 - discount_pct), 2)
    fees = calculate_amazon_fees(discounted_price, category_name, fba_fee, shipping_cost, plan_professional)
    
    total_cost = cost + (shipping_cost if not fba_fee else 0)
    profit = discounted_price - total_cost - fees["total_fees"]
    profit_margin = (profit / discounted_price) * 100 if discounted_price > 0 else 0
    
    return {
        "base_price": base_price,
        "discounted_price": discounted_price,
        "discount_amount": round(base_price - discounted_price, 2),
        "discount_pct": discount_pct * 100,
        "fees": fees,
        "profit": round(profit, 2),
        "profit_margin": round(profit_margin, 2),
        "profit_pct_cost": round((profit / cost) * 100, 2) if cost > 0 else 0,
        "total_cost": total_cost,
    }

# ============================================================
# SHOPIFY SYNC — MOREKASHOP1
# ============================================================
@st.cache_data(ttl=300)
def fetch_shopify_products():
    """Obtiene productos de morekashop1 con costos."""
    try:
        # Token desde Streamlit Secrets o variable de entorno
        token = st.secrets.get("shopify", {}).get("MOREKA_ACCESS_TOKEN", 
               os.getenv("SHOPIFY_MOREKA_TOKEN", ""))
        if not token:
            st.error("❌ Token de Shopify no configurado. Agrega `SHOPIFY_MOREKA_TOKEN` a los Secrets de Streamlit.")
            return []
        
        shop = "morekashop1"
        version = "2025-01"
        base_url = f"https://{shop}.myshopify.com/admin/api/{version}"
        headers = {"X-Shopify-Access-Token": token}
        
        products = []
        inventory_item_ids = []
        
        # FASE 1: Obtener productos
        url = f"{base_url}/products.json?limit=250"
        page_count = 0
        
        while url and page_count < 20:  # Max 5000 products
            page_count += 1
            try:
                r = requests.get(url, headers=headers, timeout=30)
                if r.status_code != 200:
                    st.error(f"Error Shopify: {r.status_code} - {r.text[:200]}")
                    return []
                
                data = r.json()
                for product in data.get("products", []):
                    for variant in product.get("variants", []):
                        inv_id = variant.get("inventory_item_id")
                        products.append({
                            "ID": product.get("id"),
                            "Título": product.get("title", ""),
                            "Tipo": product.get("product_type", ""),
                            "Vendor": product.get("vendor", ""),
                            "SKU": variant.get("sku") or "Sin SKU",
                            "Variante": variant.get("title", ""),
                            "Costo": None,
                            "Precio Shopify": float(variant.get("price", 0) or 0),
                            "Status": product.get("status", ""),
                            "Inventory Item ID": inv_id,
                        })
                        if inv_id:
                            inventory_item_ids.append(inv_id)
                
                # Paginación
                link_header = r.headers.get("Link", "")
                url = None
                if 'rel="next"' in link_header:
                    for part in link_header.split(","):
                        if 'rel="next"' in part:
                            url = part.split(";")[0].strip().strip("<").strip(">")
                            break
                
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                st.error(f"Error en página {page_count}: {e}")
                break
        
        # FASE 2: Obtener costos en batch
        if inventory_item_ids:
            chunk_size = 250
            cost_map = {}
            
            for i in range(0, len(inventory_item_ids), chunk_size):
                chunk = inventory_item_ids[i:i + chunk_size]
                ids_str = ",".join(str(cid) for cid in chunk)
                
                batch_url = f"{base_url}/inventory_items.json?ids={ids_str}&limit=250"
                try:
                    br = requests.get(batch_url, headers=headers, timeout=30)
                    if br.status_code == 200:
                        for item in br.json().get("inventory_items", []):
                            item_id = item.get("id")
                            cost_str = item.get("cost")
                            if cost_str and item_id:
                                try:
                                    cost_map[item_id] = float(cost_str)
                                except:
                                    pass
                    time.sleep(0.5)
                except Exception as e:
                    st.warning(f"Error batch {i}: {e}")
            
            # Asignar costos
            for p in products:
                inv_id = p["Inventory Item ID"]
                if inv_id and inv_id in cost_map:
                    p["Costo"] = cost_map[inv_id]
        
        return products
    except Exception as e:
        st.error(f"Error conectando a Shopify: {e}")
        return []

# ============================================================
# SIDEBAR — CONFIGURACIÓN GLOBAL
# ============================================================
with st.sidebar:
    st.markdown("### ⚙️ Configuración México 2026")
    
    st.markdown("---")
    st.markdown("#### 🏢 Datos Fiscales")
    has_rfc = st.checkbox("Tengo RFC registrado en ML", value=True)
    if not has_rfc:
        st.markdown("<div class='danger-box'>⚠️ Sin RFC: ISR 20% + IVA 16% (no recuperables)</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("#### 📦 Mercado Libre")
    ml_listing_type = st.radio(
        "Tipo de Publicación",
        ["Clásica", "Premium"],
        index=0
    )
    ml_listing_type = "classic" if ml_listing_type == "Clásica" else "premium"
    
    ml_shipping = st.radio(
        "Envío ML",
        ["Gratis (vendedor paga)", "Comprador paga"],
        index=0
    )
    ml_shipping_cost = st.number_input(
        "Costo de envío promedio (MXN)",
        value=80.0,
        min_value=0.0,
        step=10.0
    ) if ml_shipping == "Gratis (vendedor paga)" else 0
    
    st.markdown("---")
    st.markdown("#### 🟠 Amazon")
    amazon_plan = st.radio(
        "Plan Amazon",
        ["Profesional ($600/mes)", "Individual ($10/venta)"],
        index=0
    )
    plan_professional = amazon_plan == "Profesional ($600/mes)"
    
    use_fba = st.checkbox("Usar FBA", value=False)
    fba_cost_per_unit = st.number_input(
        "Costo FBA por unidad (MXN)",
        value=0.0,
        min_value=0.0,
        step=5.0,
        disabled=not use_fba
    )
    amazon_shipping = st.number_input(
        "Costo de envío FBM por unidad (MXN)",
        value=40.0,
        min_value=0.0,
        step=10.0,
        disabled=use_fba
    )
    
    st.markdown("---")
    st.markdown("#### 🎯 Descuentos")
    discount_levels = st.multiselect(
        "Niveles de descuento a evaluar",
        [5, 10, 15, 20, 25, 30, 40, 50],
        default=[10, 20, 30]
    )

# ============================================================
# HEADER PRINCIPAL
# ============================================================
st.markdown('<div class="main-header">💰 Marketplace Pricing Calculator México 2026</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Calcula precios óptimos con comisiones reales de Mercado Libre y Amazon México</div>', unsafe_allow_html=True)

# Info banner
st.markdown("""
<div class="success-box">
    ✅ <b>Comisiones actualizadas 2026:</b> ML (Clásica 8-15% / Premium 12.5-20.5%) + IVA/ISR retenidos | 
    Amazon (8-20% + FBA/FBM) | Fuente: SAT / Mercado Libre / Amazon Seller Central
</div>
""", unsafe_allow_html=True)

# ============================================================
# TABS PRINCIPALES
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "🧮 Calculadora Manual",
    "📊 Comparador ML vs Amazon",
    "🔄 Sincronizar Shopify"
])

# ============================================================
# TAB 1: CALCULADORA MANUAL
# ============================================================
with tab1:
    st.markdown("### 🧮 Calculadora Manual por Producto")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📦 Producto")
        product_name = st.text_input("Nombre del producto", "Ej: Audífonos Bluetooth NEBRO WE017")
        cost = st.number_input(
            "💵 Costo del producto (MXN)",
            value=150.0,
            min_value=0.0,
            step=10.0
        )
        target_margin = st.slider(
            "🎯 Margen de ganancia deseado (%)",
            min_value=0,
            max_value=80,
            value=30
        ) / 100
    
    with col2:
        st.markdown("#### 📋 Categorías")
        ml_category = st.selectbox(
            "Categoría Mercado Libre",
            list(ML_CATEGORIES.keys()),
            key="ml_cat_manual"
        )
        az_category = st.selectbox(
            "Categoría Amazon",
            list(AMAZON_CATEGORIES.keys()),
            key="az_cat_manual"
        )
    
    st.markdown("---")
    
    # ========== MERCADO LIBRE ==========
    st.markdown("### 🟡 Mercado Libre")
    
    ml_base_price = calculate_ml_price_from_cost(
        cost, target_margin, ml_category, ml_listing_type, has_rfc, ml_shipping_cost
    )
    
    if ml_base_price:
        ml_fees = calculate_ml_fees(ml_base_price, ml_category, ml_listing_type, has_rfc)
        ml_profit = ml_fees["net_received"] - cost - ml_shipping_cost
        ml_profit_margin = (ml_profit / ml_base_price) * 100
        
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base ML</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${ml_base_price:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
        with m2:
            st.markdown(f'''
                <div class="metric-card-green">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia Neta</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${ml_profit:,.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        with m3:
            st.markdown(f'''
                <div class="metric-card-orange">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Margen Real</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{ml_profit_margin:.1f}%</div>
                </div>
            ''', unsafe_allow_html=True)
        with m4:
            st.markdown(f'''
                <div class="metric-card-blue">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Comisiones Totales</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${ml_fees["total_fees"]:,.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        # Fee breakdown
        with st.expander("📋 Desglose de comisiones ML"):
            fee_col1, fee_col2 = st.columns(2)
            with fee_col1:
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>Comisión ML ({ml_fees['commission_rate']*100:.1f}%):</b> ${ml_fees['commission']:,.2f}<br>
                    <b>Costo fijo:</b> ${ml_fees['fixed_fee']:,.2f}<br>
                    <b>Base gravable:</b> ${ml_fees['base_gravable']:,.2f}<br>
                </div>
                """, unsafe_allow_html=True)
            with fee_col2:
                iva_label = "8% (con RFC)" if has_rfc else "16% (sin RFC)"
                isr_label = "2.5% (con RFC)" if has_rfc else "20% (sin RFC)"
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>IVA retenido ({iva_label}):</b> ${ml_fees['iva_ret']:,.2f}<br>
                    <b>ISR retenido ({isr_label}):</b> ${ml_fees['isr_ret']:,.2f}<br>
                    <b>Total:</b> ${ml_fees['total_fees']:,.2f} ({(ml_fees['total_fees']/ml_base_price)*100:.1f}%)
                </div>
                """, unsafe_allow_html=True)
        
        # Discount scenarios
        if discount_levels:
            st.markdown("#### 🏷️ Escenarios con Descuento")
            
            discount_data = []
            for d_pct in [d/100 for d in discount_levels]:
                result = calculate_ml_with_discount(cost, ml_base_price, d_pct, ml_category, ml_listing_type, has_rfc, ml_shipping_cost)
                discount_data.append(result)
            
            df_discount = pd.DataFrame([
                {
                    "Descuento": f"{d['discount_pct']:.0f}%",
                    "Precio Original": f"${d['base_price']:,.2f}",
                    "Precio con Descuento": f"${d['discounted_price']:,.2f}",
                    "Monto Descuento": f"${d['discount_amount']:,.2f}",
                    "Comisiones": f"${d['fees']['total_fees']:,.2f}",
                    "Ganancia": f"${d['profit']:,.2f}",
                    "Margen": f"{d['profit_margin']:.1f}%",
                    "ROI": f"{d['profit_pct_cost']:.1f}%",
                }
                for d in discount_data
            ])
            
            st.dataframe(df_discount, use_container_width=True, hide_index=True)
            
            for d in discount_data:
                if d["profit"] < 0:
                    st.error(f"⚠️ Con {d['discount_pct']:.0f}% de descuento **PIERDES** ${abs(d['profit']):,.2f} por unidad. ¡No recomendado!")
                elif d["profit_margin"] < 10:
                    st.warning(f"⚠️ Con {d['discount_pct']:.0f}% de descuento tu margen es solo {d['profit_margin']:.1f}%. Margen bajo.")
    else:
        st.error("❌ El margen deseado + comisiones + impuestos superan el 100%. Reduce el margen o verifica las comisiones.")
    
    st.markdown("---")
    
    # ========== AMAZON ==========
    st.markdown("### 🟠 Amazon México")
    
    az_fba = fba_cost_per_unit if use_fba else 0
    az_ship = 0 if use_fba else amazon_shipping
    
    az_base_price = calculate_amazon_price_from_cost(
        cost, target_margin, az_category, az_fba, az_ship, plan_professional
    )
    
    if az_base_price:
        az_fees = calculate_amazon_fees(az_base_price, az_category, az_fba, az_ship, plan_professional)
        az_profit = az_fees["net_received"] - cost - az_ship
        az_profit_margin = (az_profit / az_base_price) * 100
        
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Amazon</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${az_base_price:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
        with a2:
            st.markdown(f'''
                <div class="metric-card-green">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia Neta</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${az_profit:,.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        with a3:
            st.markdown(f'''
                <div class="metric-card-orange">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Margen Real</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{az_profit_margin:.1f}%</div>
                </div>
            ''', unsafe_allow_html=True)
        with a4:
            st.markdown(f'''
                <div class="metric-card-blue">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Comisiones Totales</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${az_fees["total_fees"]:,.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        with st.expander("📋 Desglose de comisiones Amazon"):
            fee_col1, fee_col2 = st.columns(2)
            with fee_col1:
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>Referral Fee ({az_fees['referral_rate']*100:.0f}%):</b> ${az_fees['referral']:,.2f}<br>
                    <b>Tarifa mínima:</b> ${az_fees['min_fee']:,.2f}<br>
                    <b>Plan prorrateado:</b> ${az_fees['plan_fee']:,.2f}<br>
                </div>
                """, unsafe_allow_html=True)
            with fee_col2:
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>FBA:</b> ${az_fees['fba']:,.2f}<br>
                    <b>Envío:</b> ${az_fees['shipping']:,.2f}<br>
                    <b>Total:</b> ${az_fees['total_fees']:,.2f} ({(az_fees['total_fees']/az_base_price)*100:.1f}%)
                </div>
                """, unsafe_allow_html=True)
        
        if discount_levels:
            st.markdown("#### 🏷️ Escenarios con Descuento")
            
            az_discount_data = []
            for d_pct in [d/100 for d in discount_levels]:
                result = calculate_amazon_with_discount(cost, az_base_price, d_pct, az_category, az_fba, az_ship, plan_professional)
                az_discount_data.append(result)
            
            df_az_discount = pd.DataFrame([
                {
                    "Descuento": f"{d['discount_pct']:.0f}%",
                    "Precio Original": f"${d['base_price']:,.2f}",
                    "Precio con Descuento": f"${d['discounted_price']:,.2f}",
                    "Monto Descuento": f"${d['discount_amount']:,.2f}",
                    "Comisiones": f"${d['fees']['total_fees']:,.2f}",
                    "Ganancia": f"${d['profit']:,.2f}",
                    "Margen": f"{d['profit_margin']:.1f}%",
                    "ROI": f"{d['profit_pct_cost']:.1f}%",
                }
                for d in az_discount_data
            ])
            
            st.dataframe(df_az_discount, use_container_width=True, hide_index=True)
            
            for d in az_discount_data:
                if d["profit"] < 0:
                    st.error(f"⚠️ Con {d['discount_pct']:.0f}% de descuento en Amazon **PIERDES** ${abs(d['profit']):,.2f} por unidad.")
                elif d["profit_margin"] < 10:
                    st.warning(f"⚠️ Con {d['discount_pct']:.0f}% de descuento en Amazon tu margen es solo {d['profit_margin']:.1f}%.")
    else:
        st.error("❌ El margen deseado + comisiones superan el 100%. Reduce el margen o verifica las comisiones.")

# ============================================================
# TAB 2: COMPARADOR
# ============================================================
with tab2:
    st.markdown("### 📊 Comparador ML vs Amazon — Mismo Producto")
    
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    
    with comp_col1:
        comp_cost = st.number_input("💵 Costo (MXN)", value=150.0, min_value=0.0, step=10.0, key="comp_cost")
        comp_margin = st.slider("🎯 Margen deseado (%)", 0, 80, 30, key="comp_margin") / 100
    
    with comp_col2:
        comp_ml_cat = st.selectbox("Categoría ML", list(ML_CATEGORIES.keys()), key="comp_ml_cat")
    
    with comp_col3:
        comp_az_cat = st.selectbox("Categoría Amazon", list(AMAZON_CATEGORIES.keys()), key="comp_az_cat")
    
    comp_ml_price = calculate_ml_price_from_cost(
        comp_cost, comp_margin, comp_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost
    )
    comp_az_price = calculate_amazon_price_from_cost(
        comp_cost, comp_margin, comp_az_cat, 
        fba_cost_per_unit if use_fba else 0, 
        0 if use_fba else amazon_shipping, 
        plan_professional
    )
    
    if comp_ml_price and comp_az_price:
        comp_ml_fees = calculate_ml_fees(comp_ml_price, comp_ml_cat, ml_listing_type, has_rfc)
        comp_az_fees = calculate_amazon_fees(comp_az_price, comp_az_cat, 
            fba_cost_per_unit if use_fba else 0, 
            0 if use_fba else amazon_shipping, 
            plan_professional)
        
        comp_ml_profit = comp_ml_fees["net_received"] - comp_cost - ml_shipping_cost
        comp_az_profit = comp_az_fees["net_received"] - comp_cost - (0 if use_fba else amazon_shipping)
        
        comp_ml_margin = (comp_ml_profit / comp_ml_price) * 100
        comp_az_margin = (comp_az_profit / comp_az_price) * 100
        
        st.markdown("---")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 🟡 Mercado Libre")
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Recomendado</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_ml_price:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Ganancia neta:** ${comp_ml_profit:,.2f} ({comp_ml_margin:.1f}%)
            - **Comisiones totales:** ${comp_ml_fees['total_fees']:,.2f} ({(comp_ml_fees['total_fees']/comp_ml_price)*100:.1f}%)
            - **Comisión ML:** {comp_ml_fees['commission_rate']*100:.1f}%
            - **IVA retenido:** ${comp_ml_fees['iva_ret']:,.2f}
            - **ISR retenido:** ${comp_ml_fees['isr_ret']:,.2f}
            - **Envío:** {'Gratis (vendedor paga $' + f'{ml_shipping_cost:,.0f}' + ')' if ml_shipping_cost > 0 else 'Comprador paga'}
            """)
            
            st.markdown("**Margen con descuentos:**")
            for d in [10, 20, 30]:
                d_result = calculate_ml_with_discount(comp_cost, comp_ml_price, d/100, comp_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost)
                color = "profit-positive" if d_result["profit"] > 0 else "profit-negative"
                st.markdown(f"- Con **{d}% descuento**: <span class='{color}'>${d_result['discounted_price']:,.2f}</span> → Ganancia: <span class='{color}'>${d_result['profit']:,.2f} ({d_result['profit_margin']:.1f}%)</span>", unsafe_allow_html=True)
        
        with c2:
            st.markdown("#### 🟠 Amazon")
            st.markdown(f'''
                <div class="metric-card-orange">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Recomendado</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_az_price:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Ganancia neta:** ${comp_az_profit:,.2f} ({comp_az_margin:.1f}%)
            - **Comisiones totales:** ${comp_az_fees['total_fees']:,.2f} ({(comp_az_fees['total_fees']/comp_az_price)*100:.1f}%)
            - **Referral Fee:** {comp_az_fees['referral_rate']*100:.0f}%
            - **FBA:** {'Sí ($' + f'{comp_az_fees["fba"]:,.0f}' + ')' if comp_az_fees['fba'] > 0 else 'No (FBM)'}
            - **Envío:** {'Incluido en FBA' if use_fba else f'Vendedor paga ${comp_az_fees["shipping"]:,.0f}'}
            - **Plan:** {'Profesional ($600/mes)' if plan_professional else 'Individual ($10/venta)'}
            """)
            
            st.markdown("**Margen con descuentos:**")
            for d in [10, 20, 30]:
                d_result = calculate_amazon_with_discount(comp_cost, comp_az_price, d/100, comp_az_cat, 
                    fba_cost_per_unit if use_fba else 0, 
                    0 if use_fba else amazon_shipping, 
                    plan_professional)
                color = "profit-positive" if d_result["profit"] > 0 else "profit-negative"
                st.markdown(f"- Con **{d}% descuento**: <span class='{color}'>${d_result['discounted_price']:,.2f}</span> → Ganancia: <span class='{color}'>${d_result['profit']:,.2f} ({d_result['profit_margin']:.1f}%)</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Recommendation
        if comp_ml_price < comp_az_price:
            diff = comp_az_price - comp_ml_price
            st.info(f"💡 **Mercado Libre permite un precio ${diff:,.2f} más bajo** que Amazon para el mismo margen. Ventaja competitiva en ML.")
        else:
            diff = comp_ml_price - comp_az_price
            st.info(f"💡 **Amazon permite un precio ${diff:,.2f} más bajo** que Mercado Libre para el mismo margen. Amazon puede ser más competitivo.")
        
        if comp_ml_profit > comp_az_profit:
            st.success(f"✅ **Mercado Libre es más rentable** por ${comp_ml_profit - comp_az_profit:,.2f} por unidad.")
        else:
            st.success(f"✅ **Amazon es más rentable** por ${comp_az_profit - comp_ml_profit:,.2f} por unidad.")
    
    else:
        st.error("❌ No se puede calcular. El margen + comisiones + impuestos superan el 100%.")

# ============================================================
# TAB 3: SHOPIFY SYNC
# ============================================================
with tab3:
    st.markdown("### 🔄 Sincronizar con Shopify — morekashop1")
    st.markdown("Carga automáticamente los productos de morekashop1 con sus costos para calcular precios.")
    
    if st.button("🔄 Cargar Productos de Shopify", type="primary"):
        with st.spinner("Conectando a morekashop1..."):
            products = fetch_shopify_products()
        
        if products:
            st.success(f"✅ {len(products)} productos cargados de morekashop1")
            
            # Convert to DataFrame
            df = pd.DataFrame(products)
            
            # Filter products with cost
            df_with_cost = df[df["Costo"].notna()].copy()
            df_no_cost = df[df["Costo"].isna()].copy()
            
            if len(df_no_cost) > 0:
                st.warning(f"⚠️ {len(df_no_cost)} productos sin costo registrado en Shopify")
                with st.expander("Ver productos sin costo"):
                    st.dataframe(df_no_cost[["SKU", "Título", "Precio Shopify"]], use_container_width=True, hide_index=True)
            
            if len(df_with_cost) > 0:
                st.success(f"✅ {len(df_with_cost)} productos con costo listos para calcular")
                
                # Configuration
                st.markdown("---")
                st.markdown("#### ⚙️ Configuración para cálculo masivo")
                
                bulk_margin = st.slider("Margen deseado (%)", 0, 80, 30, key="bulk_margin") / 100
                bulk_ml_cat = st.selectbox("Categoría ML por defecto", list(ML_CATEGORIES.keys()), key="bulk_ml_cat")
                bulk_az_cat = st.selectbox("Categoría Amazon por defecto", list(AMAZON_CATEGORIES.keys()), key="bulk_az_cat")
                
                if st.button("🚀 Calcular Precios para Todos", type="primary"):
                    with st.spinner("Calculando precios..."):
                        results = []
                        
                        for _, row in df_with_cost.iterrows():
                            costo = float(row["Costo"])
                            sku = row["SKU"]
                            titulo = row["Título"]
                            
                            # ML
                            ml_price = calculate_ml_price_from_cost(
                                costo, bulk_margin, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost
                            )
                            ml_fees = calculate_ml_fees(ml_price, bulk_ml_cat, ml_listing_type, has_rfc) if ml_price else None
                            ml_profit = ml_fees["net_received"] - costo - ml_shipping_cost if ml_price else 0
                            
                            # Amazon
                            az_fba = fba_cost_per_unit if use_fba else 0
                            az_ship = 0 if use_fba else amazon_shipping
                            az_price = calculate_amazon_price_from_cost(
                                costo, bulk_margin, bulk_az_cat, az_fba, az_ship, plan_professional
                            )
                            az_fees = calculate_amazon_fees(az_price, bulk_az_cat, az_fba, az_ship, plan_professional) if az_price else None
                            az_profit = az_fees["net_received"] - costo - az_ship if az_price else 0
                            
                            # Calculate discounts
                            ml_20 = calculate_ml_with_discount(costo, ml_price, 0.20, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost) if ml_price else None
                            az_20 = calculate_amazon_with_discount(costo, az_price, 0.20, bulk_az_cat, az_fba, az_ship, plan_professional) if az_price else None
                            
                            result_row = {
                                "SKU": sku,
                                "Producto": titulo,
                                "Costo": costo,
                                "ML Precio Base": round(ml_price, 2) if ml_price else 0,
                                "ML -20%": round(ml_20["discounted_price"], 2) if ml_20 else 0,
                                "ML Ganancia": round(ml_profit, 2),
                                "ML Margen": round((ml_profit/ml_price)*100, 1) if ml_price else 0,
                                "Amazon Precio Base": round(az_price, 2) if az_price else 0,
                                "Amazon -20%": round(az_20["discounted_price"], 2) if az_20 else 0,
                                "Amazon Ganancia": round(az_profit, 2),
                                "Amazon Margen": round((az_profit/az_price)*100, 1) if az_price else 0,
                            }
                            results.append(result_row)
                        
                        df_results = pd.DataFrame(results)
                        st.success(f"✅ Cálculo completado para {len(results)} productos")
                        st.dataframe(df_results, use_container_width=True, hide_index=True)
                        
                        # Download buttons
                        csv_buffer = io.StringIO()
                        df_results.to_csv(csv_buffer, index=False)
                        st.download_button(
                            "📥 Descargar CSV",
                            csv_buffer.getvalue(),
                            f"precios_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv"
                        )
                        
                        # Excel
                        try:
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df_results.to_excel(writer, index=False, sheet_name='Precios')
                            st.download_button(
                                "📥 Descargar Excel",
                                excel_buffer.getvalue(),
                                f"precios_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except:
                            st.info("📊 Excel no disponible (instalar openpyxl para habilitar)")
            else:
                st.error("❌ Ningún producto tiene costo registrado en Shopify. Verifica que los costos estén configurados en Inventory > Inventory Items.")
        else:
            st.error("❌ No se pudieron cargar productos de Shopify. Verifica la conexión.")
    
    st.markdown("---")
    st.markdown("""
    **¿Cómo configurar costos en Shopify?**
    1. Ve a **Productos > Inventario** en el admin de morekashop1
    2. Selecciona cada producto
    3. En la sección **Costo por artículo**, ingresa el costo unitario
    4. Guarda
    
    **Nota:** Los costos se leen desde `inventory_items.cost` en la API de Shopify.
    """)

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
    f"Marketplace Pricing Calculator México 2026 • Comisiones actualizadas: Junio 2026 • Fuente: SAT / ML / Amazon"
    f"</div>",
    unsafe_allow_html=True
)
