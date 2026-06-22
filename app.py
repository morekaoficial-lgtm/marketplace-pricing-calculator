#!/usr/bin/env python3
"""
Calculadora de Precios para Marketplaces — México 2026
Mercado Libre y Amazon México con comisiones reales 2026
Lógica: Calcula precio base para que precio con descuento (40-50%) mantenga margen deseado
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
    .metric-card-gold {
        background: linear-gradient(135deg, #f5af19 0%, #f12711 100%);
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
    .discount-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .discount-green { background: #d4edda; color: #155724; }
    .discount-yellow { background: #fff3cd; color: #856404; }
    .discount-red { background: #f8d7da; color: #721c24; }
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
    "Ropa, Bolsas y Calzado": {"classic": 0.15, "premium": 0.195},
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
    "Accesorios Electrónicos": 0.15,
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
    "Ropa y Accesorios": 0.15,
    "Joyas y Relojes": 0.20,
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
    
    commission = price * commission_rate
    fixed_fee = get_ml_fixed_fee(price, listing_type)
    
    base_gravable = price / 1.16
    
    if has_rfc:
        iva_ret = base_gravable * 0.08
    else:
        iva_ret = base_gravable * 0.16
    
    if has_rfc:
        isr_ret = base_gravable * 0.025
    else:
        isr_ret = price * 0.20
    
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

def calculate_ml_price_for_discount(cost, target_margin_after_discount, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0):
    """Calcula el precio BASE necesario para que el precio con descuento mantenga el margen deseado.
    
    Fórmula:
    1. Precio con descuento = Costo / (1 - margen_deseado - tarifas)
    2. Precio base = Precio con descuento / (1 - descuento)
    
    Las comisiones se calculan sobre el precio CON descuento (lo que realmente paga el cliente).
    """
    cat = ML_CATEGORIES.get(category_name, ML_CATEGORIES["Custom"])
    commission_rate = cat[listing_type]
    
    # Tarifa total aproximada sobre precio con descuento
    if has_rfc:
        tax_rate = (0.08 + 0.025) / 1.16
    else:
        tax_rate = (0.16 / 1.16) + 0.20
    
    total_fee_rate = commission_rate + tax_rate
    
    # Iteración para resolver: las comisiones dependen del precio con descuento
    # que depende del precio base, que depende del precio con descuento...
    price_discounted = cost / (1 - target_margin_after_discount - total_fee_rate)
    
    # Iterar para ajustar fixed fee y comisiones exactas
    for _ in range(10):
        fixed_fee = get_ml_fixed_fee(price_discounted, listing_type)
        fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
        total_fees = fees["total_fees"] + shipping_cost
        
        # Margen deseado sobre el precio con descuento: (price_discounted - cost - fees) / price_discounted = target_margin
        # price_discounted - cost - fees = target_margin * price_discounted
        # price_discounted * (1 - target_margin) = cost + fees
        # Pero fees dependen de price_discounted...
        # Solución iterativa
        price_discounted = (cost + total_fees) / (1 - target_margin_after_discount)
    
    # Ahora calcular precio base: price_discounted = price_base * (1 - discount)
    price_base = price_discounted / (1 - discount_pct)
    
    # Verificar con el precio base final
    price_discounted = price_base * (1 - discount_pct)
    fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
    total_fees = fees["total_fees"] + shipping_cost
    profit = price_discounted - cost - total_fees
    actual_margin = profit / price_discounted if price_discounted > 0 else 0
    
    # Ajustar si el margen no coincide exactamente
    if abs(actual_margin - target_margin_after_discount) > 0.001:
        # Reajuste final
        price_discounted = (cost + total_fees) / (1 - target_margin_after_discount)
        price_base = price_discounted / (1 - discount_pct)
    
    return round(price_base, 2), round(price_discounted, 2)

def calculate_ml_scenarios(cost, target_margin, discount_levels, category_name, listing_type="classic", has_rfc=True, shipping_cost=0):
    """Calcula precio base para que cada nivel de descuento mantenga el margen deseado."""
    results = []
    
    for discount_pct in discount_levels:
        base_price, disc_price = calculate_ml_price_for_discount(
            cost, target_margin, discount_pct, category_name, listing_type, has_rfc, shipping_cost
        )
        
        fees = calculate_ml_fees(disc_price, category_name, listing_type, has_rfc)
        total_fees = fees["total_fees"] + shipping_cost
        profit = disc_price - cost - total_fees
        margin_actual = (profit / disc_price) * 100 if disc_price > 0 else 0
        roi = (profit / cost) * 100 if cost > 0 else 0
        
        # Calcular precio base sin descuento (solo margen deseado, sin descuento)
        base_price_no_discount = disc_price / (1 - discount_pct)
        
        results.append({
            "discount_pct": discount_pct * 100,
            "base_price": base_price,
            "discounted_price": disc_price,
            "discount_amount": round(base_price - disc_price, 2),
            "fees": fees,
            "profit": round(profit, 2),
            "margin_actual": round(margin_actual, 2),
            "roi": round(roi, 2),
            "total_cost": cost + shipping_cost,
        })
    
    return results

# ============================================================
# FUNCIONES DE CÁLCULO — AMAZON MÉXICO
# ============================================================
def calculate_amazon_fees(price, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula todas las comisiones de Amazon México para un precio dado."""
    referral_rate = AMAZON_CATEGORIES.get(category_name, 0.15)
    
    referral = price * referral_rate
    min_fee = 5.0 if referral < 5 else 0
    if min_fee > 0:
        referral = max(referral, min_fee)
    
    plan_fee = 20.0 if plan_professional else 0
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

def calculate_amazon_price_for_discount(cost, target_margin_after_discount, discount_pct, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula el precio BASE necesario para que el precio con descuento mantenga el margen deseado."""
    referral_rate = AMAZON_CATEGORIES.get(category_name, 0.15)
    
    plan_fee = 20.0 if plan_professional else 0
    fba = fba_fee if fba_fee else 0
    ship = shipping_cost if not fba_fee else 0
    fixed_fees = plan_fee + fba + ship
    
    # Iteración para resolver
    price_discounted = cost / (1 - target_margin_after_discount - referral_rate)
    
    for _ in range(10):
        fees = calculate_amazon_fees(price_discounted, category_name, fba_fee, shipping_cost, plan_professional)
        total_fees = fees["total_fees"]
        price_discounted = (cost + total_fees) / (1 - target_margin_after_discount)
    
    price_base = price_discounted / (1 - discount_pct)
    
    # Verificación
    price_discounted = price_base * (1 - discount_pct)
    fees = calculate_amazon_fees(price_discounted, category_name, fba_fee, shipping_cost, plan_professional)
    total_fees = fees["total_fees"]
    profit = price_discounted - cost - total_fees
    actual_margin = profit / price_discounted if price_discounted > 0 else 0
    
    if abs(actual_margin - target_margin_after_discount) > 0.001:
        price_discounted = (cost + total_fees) / (1 - target_margin_after_discount)
        price_base = price_discounted / (1 - discount_pct)
    
    return round(price_base, 2), round(price_discounted, 2)

def calculate_amazon_scenarios(cost, target_margin, discount_levels, category_name, fba_fee=0, shipping_cost=0, plan_professional=True):
    """Calcula precio base para que cada nivel de descuento mantenga el margen deseado."""
    results = []
    
    for discount_pct in discount_levels:
        base_price, disc_price = calculate_amazon_price_for_discount(
            cost, target_margin, discount_pct, category_name, fba_fee, shipping_cost, plan_professional
        )
        
        fees = calculate_amazon_fees(disc_price, category_name, fba_fee, shipping_cost, plan_professional)
        total_fees = fees["total_fees"]
        profit = disc_price - cost - total_fees
        margin_actual = (profit / disc_price) * 100 if disc_price > 0 else 0
        roi = (profit / cost) * 100 if cost > 0 else 0
        
        results.append({
            "discount_pct": discount_pct * 100,
            "base_price": base_price,
            "discounted_price": disc_price,
            "discount_amount": round(base_price - disc_price, 2),
            "fees": fees,
            "profit": round(profit, 2),
            "margin_actual": round(margin_actual, 2),
            "roi": round(roi, 2),
            "total_cost": cost + (shipping_cost if not fba_fee else 0),
        })
    
    return results

# ============================================================
# SHOPIFY SYNC — MOREKASHOP1
# ============================================================
@st.cache_data(ttl=300)
def fetch_shopify_products():
    """Obtiene productos de morekashop1 con costos."""
    try:
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
        
        url = f"{base_url}/products.json?limit=250"
        page_count = 0
        
        while url and page_count < 20:
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
                
                link_header = r.headers.get("Link", "")
                url = None
                if 'rel="next"' in link_header:
                    for part in link_header.split(","):
                        if 'rel="next"' in part:
                            url = part.split(";")[0].strip().strip("<").strip(">")
                            break
                
                time.sleep(0.5)
            except Exception as e:
                st.error(f"Error en página {page_count}: {e}")
                break
        
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
    
    use_fba = st.checkbox("Usar Amazon FBA", value=False)
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
    st.markdown("#### 🎯 Descuentos a Calcular")
    discount_levels = st.multiselect(
        "Niveles de descuento",
        [0.40, 0.45, 0.50, 0.55, 0.60],
        default=[0.40, 0.45, 0.50],
        format_func=lambda x: f"{int(x*100)}%"
    )
    
    st.markdown("---")
    st.markdown("<div style='font-size: 0.8rem; color: #999;'>Comisiones actualizadas: Junio 2026<br>Fuente: SAT / ML / Amazon</div>", unsafe_allow_html=True)

# ============================================================
# HEADER PRINCIPAL
# ============================================================
st.markdown('<div class="main-header">💰 Marketplace Pricing Calculator México 2026</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Calcula precios base para aplicar descuentos del 40-50% manteniendo tu margen de ganancia</div>', unsafe_allow_html=True)

st.markdown("""
<div class="success-box">
    <b>💡 Cómo funciona:</b> Ingresa tu <b>costo</b> y el <b>margen que quieres GANAR después del descuento</b>. 
    La app calcula el <b>precio base</b> que debes publicar para que, al aplicar el descuento, 
    aún mantengas tu margen deseado. Las comisiones se calculan sobre el precio CON descuento.
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
            "🎯 Margen de ganancia DESPUÉS del descuento (%)",
            min_value=0,
            max_value=80,
            value=30,
            help="Este es el margen que quieres ganar sobre el precio que realmente recibes (después del descuento)"
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
    
    if discount_levels:
        ml_scenarios = calculate_ml_scenarios(
            cost, target_margin, discount_levels, ml_category, ml_listing_type, has_rfc, ml_shipping_cost
        )
        
        # Show all scenarios in a table
        df_ml = pd.DataFrame([
            {
                "Descuento": f"{s['discount_pct']:.0f}%",
                "Precio Base (Publicar)": f"${s['base_price']:,.2f}",
                "Precio con Descuento": f"${s['discounted_price']:,.2f}",
                "Monto Descuento": f"${s['discount_amount']:,.2f}",
                "Comisiones ML": f"${s['fees']['total_fees']:,.2f}",
                "Ganancia Neta": f"${s['profit']:,.2f}",
                "Margen Real": f"{s['margin_actual']:.1f}%",
                "ROI": f"{s['roi']:.1f}%",
            }
            for s in ml_scenarios
        ])
        
        st.dataframe(df_ml, use_container_width=True, hide_index=True)
        
        # Highlight the recommended base price (usually the highest discount scenario)
        if ml_scenarios:
            max_discount_scenario = ml_scenarios[-1]  # Highest discount
            
            st.markdown("#### ⭐ Precio Recomendado para Publicar")
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f'''
                    <div class="metric-card-gold">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base ML</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_discount_scenario['base_price']:,.2f} MXN</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Para aplicar hasta {max_discount_scenario['discount_pct']:.0f}% descuento</div>
                    </div>
                ''', unsafe_allow_html=True)
            with m2:
                st.markdown(f'''
                    <div class="metric-card-green">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia con {max_discount_scenario['discount_pct']:.0f}% off</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_discount_scenario['profit']:,.2f}</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Margen: {max_discount_scenario['margin_actual']:.1f}%</div>
                    </div>
                ''', unsafe_allow_html=True)
            with m3:
                st.markdown(f'''
                    <div class="metric-card-blue">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Precio con Descuento</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_discount_scenario['discounted_price']:,.2f} MXN</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Lo que paga el cliente</div>
                    </div>
                ''', unsafe_allow_html=True)
            
            # Show all discount scenarios side by side
            st.markdown("#### 🏷️ Comparación de Escenarios de Descuento")
            
            cols = st.columns(len(ml_scenarios))
            for i, s in enumerate(ml_scenarios):
                with cols[i]:
                    st.markdown(f"**{s['discount_pct']:.0f}% OFF**")
                    st.markdown(f"- **Base:** ${s['base_price']:,.2f}")
                    st.markdown(f"- **Final:** ${s['discounted_price']:,.2f}")
                    st.markdown(f"- **Ganancia:** ${s['profit']:,.2f}")
                    st.markdown(f"- **Margen:** {s['margin_actual']:.1f}%")
                    
                    if s['profit'] < 0:
                        st.markdown("<span class='profit-negative'>❌ PÉRDIDA</span>", unsafe_allow_html=True)
                    elif s['margin_actual'] < 10:
                        st.markdown("<span class='profit-negative'>⚠️ Margen bajo</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='profit-positive'>✅ Rentable</span>", unsafe_allow_html=True)
            
            # Fee breakdown for the highest discount scenario
            with st.expander("📋 Desglose de comisiones ML (al precio con descuento)"):
                s = max_discount_scenario
                fee_col1, fee_col2 = st.columns(2)
                with fee_col1:
                    st.markdown(f"""
                    <div class="fee-breakdown">
                        <b>Comisión ML ({s['fees']['commission_rate']*100:.1f}%):</b> ${s['fees']['commission']:,.2f}<br>
                        <b>Costo fijo:</b> ${s['fees']['fixed_fee']:,.2f}<br>
                        <b>Base gravable:</b> ${s['fees']['base_gravable']:,.2f}<br>
                    </div>
                    """, unsafe_allow_html=True)
                with fee_col2:
                    iva_label = "8% (con RFC)" if has_rfc else "16% (sin RFC)"
                    isr_label = "2.5% (con RFC)" if has_rfc else "20% (sin RFC)"
                    st.markdown(f"""
                    <div class="fee-breakdown">
                        <b>IVA retenido ({iva_label}):</b> ${s['fees']['iva_ret']:,.2f}<br>
                        <b>ISR retenido ({isr_label}):</b> ${s['fees']['isr_ret']:,.2f}<br>
                        <b>Envío:</b> ${ml_shipping_cost:,.2f}<br>
                        <b><b>Total comisiones:</b></b> ${s['fees']['total_fees']:,.2f} + Envío ${ml_shipping_cost:,.2f}
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("Selecciona al menos un nivel de descuento en la sidebar")
    
    st.markdown("---")
    
    # ========== AMAZON ==========
    st.markdown("### 🟠 Amazon México")
    
    az_fba = fba_cost_per_unit if use_fba else 0
    az_ship = 0 if use_fba else amazon_shipping
    
    if discount_levels:
        az_scenarios = calculate_amazon_scenarios(
            cost, target_margin, discount_levels, az_category, az_fba, az_ship, plan_professional
        )
        
        df_az = pd.DataFrame([
            {
                "Descuento": f"{s['discount_pct']:.0f}%",
                "Precio Base (Publicar)": f"${s['base_price']:,.2f}",
                "Precio con Descuento": f"${s['discounted_price']:,.2f}",
                "Monto Descuento": f"${s['discount_amount']:,.2f}",
                "Comisiones Amazon": f"${s['fees']['total_fees']:,.2f}",
                "Ganancia Neta": f"${s['profit']:,.2f}",
                "Margen Real": f"{s['margin_actual']:.1f}%",
                "ROI": f"{s['roi']:.1f}%",
            }
            for s in az_scenarios
        ])
        
        st.dataframe(df_az, use_container_width=True, hide_index=True)
        
        if az_scenarios:
            max_az_scenario = az_scenarios[-1]
            
            st.markdown("#### ⭐ Precio Recomendado para Publicar")
            
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown(f'''
                    <div class="metric-card-gold">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Amazon</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_az_scenario['base_price']:,.2f} MXN</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Para aplicar hasta {max_az_scenario['discount_pct']:.0f}% descuento</div>
                    </div>
                ''', unsafe_allow_html=True)
            with a2:
                st.markdown(f'''
                    <div class="metric-card-green">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia con {max_az_scenario['discount_pct']:.0f}% off</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_az_scenario['profit']:,.2f}</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Margen: {max_az_scenario['margin_actual']:.1f}%</div>
                    </div>
                ''', unsafe_allow_html=True)
            with a3:
                st.markdown(f'''
                    <div class="metric-card-blue">
                        <div style="font-size: 0.9rem; opacity: 0.9;">Precio con Descuento</div>
                        <div style="font-size: 2.2rem; font-weight: 700;">${max_az_scenario['discounted_price']:,.2f} MXN</div>
                        <div style="font-size: 0.85rem; opacity: 0.9;">Lo que paga el cliente</div>
                    </div>
                ''', unsafe_allow_html=True)
            
            st.markdown("#### 🏷️ Comparación de Escenarios de Descuento")
            
            cols = st.columns(len(az_scenarios))
            for i, s in enumerate(az_scenarios):
                with cols[i]:
                    st.markdown(f"**{s['discount_pct']:.0f}% OFF**")
                    st.markdown(f"- **Base:** ${s['base_price']:,.2f}")
                    st.markdown(f"- **Final:** ${s['discounted_price']:,.2f}")
                    st.markdown(f"- **Ganancia:** ${s['profit']:,.2f}")
                    st.markdown(f"- **Margen:** {s['margin_actual']:.1f}%")
                    
                    if s['profit'] < 0:
                        st.markdown("<span class='profit-negative'>❌ PÉRDIDA</span>", unsafe_allow_html=True)
                    elif s['margin_actual'] < 10:
                        st.markdown("<span class='profit-negative'>⚠️ Margen bajo</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='profit-positive'>✅ Rentable</span>", unsafe_allow_html=True)
            
            with st.expander("📋 Desglose de comisiones Amazon (al precio con descuento)"):
                s = max_az_scenario
                fee_col1, fee_col2 = st.columns(2)
                with fee_col1:
                    st.markdown(f"""
                    <div class="fee-breakdown">
                        <b>Referral Fee ({s['fees']['referral_rate']*100:.0f}%):</b> ${s['fees']['referral']:,.2f}<br>
                        <b>Tarifa mínima:</b> ${s['fees']['min_fee']:,.2f}<br>
                        <b>Plan prorrateado:</b> ${s['fees']['plan_fee']:,.2f}<br>
                    </div>
                    """, unsafe_allow_html=True)
                with fee_col2:
                    st.markdown(f"""
                    <div class="fee-breakdown">
                        <b>FBA:</b> ${s['fees']['fba']:,.2f}<br>
                        <b>Envío:</b> ${s['fees']['shipping']:,.2f}<br>
                        <b>Total:</b> ${s['fees']['total_fees']:,.2f} ({(s['fees']['total_fees']/s['discounted_price'])*100:.1f}%)
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("Selecciona al menos un nivel de descuento en la sidebar")

# ============================================================
# TAB 2: COMPARADOR
# ============================================================
with tab2:
    st.markdown("### 📊 Comparador ML vs Amazon — Mismo Producto")
    st.markdown("Compara el precio base necesario para aplicar descuentos en ambos marketplaces.")
    
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    
    with comp_col1:
        comp_cost = st.number_input("💵 Costo (MXN)", value=150.0, min_value=0.0, step=10.0, key="comp_cost")
        comp_margin = st.slider("🎯 Margen deseado DESPUÉS del descuento (%)", 0, 80, 30, key="comp_margin") / 100
    
    with comp_col2:
        comp_ml_cat = st.selectbox("Categoría ML", list(ML_CATEGORIES.keys()), key="comp_ml_cat")
        comp_discount = st.selectbox(
            "Nivel de descuento a comparar",
            [0.40, 0.45, 0.50, 0.55, 0.60],
            index=2,
            format_func=lambda x: f"{int(x*100)}%",
            key="comp_discount"
        )
    
    with comp_col3:
        comp_az_cat = st.selectbox("Categoría Amazon", list(AMAZON_CATEGORIES.keys()), key="comp_az_cat")
    
    comp_az_fba = fba_cost_per_unit if use_fba else 0
    comp_az_ship = 0 if use_fba else amazon_shipping
    
    # Calculate for the selected discount level
    comp_ml_base, comp_ml_disc = calculate_ml_price_for_discount(
        comp_cost, comp_margin, comp_discount, comp_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost
    )
    comp_az_base, comp_az_disc = calculate_amazon_price_for_discount(
        comp_cost, comp_margin, comp_discount, comp_az_cat, comp_az_fba, comp_az_ship, plan_professional
    )
    
    if comp_ml_base and comp_az_base:
        comp_ml_fees = calculate_ml_fees(comp_ml_disc, comp_ml_cat, ml_listing_type, has_rfc)
        comp_az_fees = calculate_amazon_fees(comp_az_disc, comp_az_cat, comp_az_fba, comp_az_ship, plan_professional)
        
        comp_ml_profit = comp_ml_disc - comp_cost - comp_ml_fees["total_fees"] - ml_shipping_cost
        comp_az_profit = comp_az_disc - comp_cost - comp_az_fees["total_fees"] - (0 if use_fba else amazon_shipping)
        
        comp_ml_margin = (comp_ml_profit / comp_ml_disc) * 100 if comp_ml_disc > 0 else 0
        comp_az_margin = (comp_az_profit / comp_az_disc) * 100 if comp_az_disc > 0 else 0
        
        st.markdown("---")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 🟡 Mercado Libre")
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base (Publicar)</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_ml_base:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Precio con {int(comp_discount*100)}% OFF:** ${comp_ml_disc:,.2f}
            - **Ganancia neta:** ${comp_ml_profit:,.2f} ({comp_ml_margin:.1f}%)
            - **Comisiones totales:** ${comp_ml_fees['total_fees']:,.2f} ({(comp_ml_fees['total_fees']/comp_ml_disc)*100:.1f}%)
            - **Comisión ML:** {comp_ml_fees['commission_rate']*100:.1f}%
            - **IVA retenido:** ${comp_ml_fees['iva_ret']:,.2f}
            - **ISR retenido:** ${comp_ml_fees['isr_ret']:,.2f}
            - **Envío:** {'Gratis (vendedor paga $' + f'{ml_shipping_cost:,.0f}' + ')' if ml_shipping_cost > 0 else 'Comprador paga'}
            """)
        
        with c2:
            st.markdown("#### 🟠 Amazon")
            st.markdown(f'''
                <div class="metric-card-orange">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base (Publicar)</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_az_base:,.2f} MXN</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Precio con {int(comp_discount*100)}% OFF:** ${comp_az_disc:,.2f}
            - **Ganancia neta:** ${comp_az_profit:,.2f} ({comp_az_margin:.1f}%)
            - **Comisiones totales:** ${comp_az_fees['total_fees']:,.2f} ({(comp_az_fees['total_fees']/comp_az_disc)*100:.1f}%)
            - **Referral Fee:** {comp_az_fees['referral_rate']*100:.0f}%
            - **FBA:** {'Sí ($' + f'{comp_az_fees["fba"]:,.0f}' + ')' if comp_az_fees['fba'] > 0 else 'No (FBM)'}
            - **Envío:** {'Incluido en FBA' if use_fba else f'Vendedor paga ${comp_az_fees["shipping"]:,.0f}'}
            - **Plan:** {'Profesional ($600/mes)' if plan_professional else 'Individual ($10/venta)'}
            """)
        
        st.markdown("---")
        
        # Recommendation
        if comp_ml_base < comp_az_base:
            diff = comp_az_base - comp_ml_base
            st.info(f"💡 **Mercado Libre requiere un precio base ${diff:,.2f} más bajo** que Amazon para el mismo margen con {int(comp_discount*100)}% de descuento. Ventaja competitiva en ML.")
        else:
            diff = comp_ml_base - comp_az_base
            st.info(f"💡 **Amazon requiere un precio base ${diff:,.2f} más bajo** que Mercado Libre para el mismo margen con {int(comp_discount*100)}% de descuento. Amazon puede ser más competitivo.")
        
        if comp_ml_profit > comp_az_profit:
            st.success(f"✅ **Mercado Libre es más rentable** por ${comp_ml_profit - comp_az_profit:,.2f} por unidad con {int(comp_discount*100)}% OFF.")
        else:
            st.success(f"✅ **Amazon es más rentable** por ${comp_az_profit - comp_ml_profit:,.2f} por unidad con {int(comp_discount*100)}% OFF.")
    
    else:
        st.error("❌ No se puede calcular. El margen + comisiones + impuestos superan el 100%.")

# ============================================================
# TAB 3: SHOPIFY SYNC
# ============================================================
with tab3:
    st.markdown("### 🔄 Sincronizar con Shopify — morekashop1")
    st.markdown("Carga automáticamente los productos de morekashop1 con sus costos para calcular precios con descuento.")
    
    if st.button("🔄 Cargar Productos de Shopify", type="primary"):
        with st.spinner("Conectando a morekashop1..."):
            products = fetch_shopify_products()
        
        if products:
            st.success(f"✅ {len(products)} productos cargados de morekashop1")
            
            df = pd.DataFrame(products)
            
            df_with_cost = df[df["Costo"].notna()].copy()
            df_no_cost = df[df["Costo"].isna()].copy()
            
            if len(df_no_cost) > 0:
                st.warning(f"⚠️ {len(df_no_cost)} productos sin costo registrado en Shopify")
                with st.expander("Ver productos sin costo"):
                    st.dataframe(df_no_cost[["SKU", "Título", "Precio Shopify"]], use_container_width=True, hide_index=True)
            
            if len(df_with_cost) > 0:
                st.success(f"✅ {len(df_with_cost)} productos con costo listos para calcular")
                
                st.markdown("---")
                st.markdown("#### ⚙️ Configuración para cálculo masivo")
                
                bulk_margin = st.slider("Margen deseado DESPUÉS del descuento (%)", 0, 80, 30, key="bulk_margin") / 100
                bulk_discount = st.selectbox(
                    "Nivel de descuento a calcular",
                    [0.40, 0.45, 0.50, 0.55, 0.60],
                    index=2,
                    format_func=lambda x: f"{int(x*100)}%",
                    key="bulk_discount"
                )
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
                            ml_base, ml_disc = calculate_ml_price_for_discount(
                                costo, bulk_margin, bulk_discount, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost
                            )
                            ml_fees = calculate_ml_fees(ml_disc, bulk_ml_cat, ml_listing_type, has_rfc)
                            ml_profit = ml_disc - costo - ml_fees["total_fees"] - ml_shipping_cost
                            
                            # Amazon
                            az_fba = fba_cost_per_unit if use_fba else 0
                            az_ship = 0 if use_fba else amazon_shipping
                            az_base, az_disc = calculate_amazon_price_for_discount(
                                costo, bulk_margin, bulk_discount, bulk_az_cat, az_fba, az_ship, plan_professional
                            )
                            az_fees = calculate_amazon_fees(az_disc, bulk_az_cat, az_fba, az_ship, plan_professional)
                            az_profit = az_disc - costo - az_fees["total_fees"] - (0 if use_fba else amazon_shipping)
                            
                            result_row = {
                                "SKU": sku,
                                "Producto": titulo,
                                "Costo": costo,
                                "ML Precio Base": round(ml_base, 2),
                                "ML Precio con {int(bulk_discount*100)}% OFF": round(ml_disc, 2),
                                "ML Ganancia": round(ml_profit, 2),
                                "ML Margen": round((ml_profit/ml_disc)*100, 1) if ml_disc else 0,
                                "Amazon Precio Base": round(az_base, 2),
                                "Amazon Precio con {int(bulk_discount*100)}% OFF": round(az_disc, 2),
                                "Amazon Ganancia": round(az_profit, 2),
                                "Amazon Margen": round((az_profit/az_disc)*100, 1) if az_disc else 0,
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
                            f"precios_marketplace_{int(bulk_discount*100)}off_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv"
                        )
                        
                        try:
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df_results.to_excel(writer, index=False, sheet_name=f'Precios_{int(bulk_discount*100)}OFF')
                            st.download_button(
                                "📥 Descargar Excel",
                                excel_buffer.getvalue(),
                                f"precios_marketplace_{int(bulk_discount*100)}off_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except:
                            st.info("📊 Excel no disponible (instalar openpyxl)")
            else:
                st.error("❌ Ningún producto tiene costo registrado en Shopify.")
        else:
            st.error("❌ No se pudieron cargar productos de Shopify.")
    
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
    f"Marketplace Pricing Calculator México 2026 • Precios base para descuentos 40-50% • Comisiones actualizadas: Junio 2026"
    f"</div>",
    unsafe_allow_html=True
)
