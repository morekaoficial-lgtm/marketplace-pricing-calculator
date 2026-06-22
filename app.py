#!/usr/bin/env python3
"""
Calculadora de Precios para Marketplaces — Mercado Libre & Amazon
Calcula precios óptimos considerando comisiones, envío y descuentos.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Marketplace Pricing Calculator",
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #667eea !important;
        color: white !important;
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
# COMISIONES POR CATEGORÍA — MERCADO LIBRE
# ============================================================
ML_CATEGORIES = {
    "Electrónica": {
        "commission": 0.15,
        "shipping": "free",  # free or buyer_pays
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Celulares y Telefonía": {
        "commission": 0.13,
        "shipping": "free",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Computación": {
        "commission": 0.14,
        "shipping": "free",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Audio y Video": {
        "commission": 0.15,
        "shipping": "free",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Accesorios para Vehículos": {
        "commission": 0.16,
        "shipping": "buyer_pays",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Hogar y Muebles": {
        "commission": 0.16,
        "shipping": "buyer_pays",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Deportes y Fitness": {
        "commission": 0.16,
        "shipping": "buyer_pays",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Juegos y Juguetes": {
        "commission": 0.16,
        "shipping": "buyer_pays",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
    "Custom": {
        "commission": 0.15,
        "shipping": "free",
        "mercado_pago": 0.0199,
        "iva_on_fees": 0.16,
    },
}

# ============================================================
# COMISIONES POR CATEGORÍA — AMAZON
# ============================================================
AMAZON_CATEGORIES = {
    "Electrónica": {
        "referral": 0.08,
        "closing": 0.00,
        "fba": 0.00,  # FBA fee per unit (will be calculated)
        "shipping": 0.00,  # If FBM
    },
    "Celulares y Accesorios": {
        "referral": 0.08,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Computadoras": {
        "referral": 0.08,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Audio y Video": {
        "referral": 0.08,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Instrumentos Musicales": {
        "referral": 0.15,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Hogar y Cocina": {
        "referral": 0.15,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Deportes y Aire Libre": {
        "referral": 0.15,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Juguetes y Juegos": {
        "referral": 0.15,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
    "Custom": {
        "referral": 0.15,
        "closing": 0.00,
        "fba": 0.00,
        "shipping": 0.00,
    },
}

# ============================================================
# FUNCIONES DE CÁLCULO — MERCADO LIBRE
# ============================================================
def calculate_ml_fees(price, category_config, shipping_cost=0):
    """Calcula todas las comisiones de Mercado Libre para un precio dado."""
    commission = price * category_config["commission"]
    mercado_pago = price * category_config["mercado_pago"]
    
    # IVA sobre comisiones
    fees_subtotal = commission + mercado_pago
    iva_fees = fees_subtotal * category_config["iva_on_fees"]
    
    total_fees = fees_subtotal + iva_fees
    
    if category_config["shipping"] == "free":
        total_fees += shipping_cost
    
    return {
        "commission": commission,
        "mercado_pago": mercado_pago,
        "iva_on_fees": iva_fees,
        "shipping": shipping_cost if category_config["shipping"] == "free" else 0,
        "total_fees": total_fees,
    }

def calculate_ml_price(cost, target_margin, category_config, shipping_cost=0):
    """Calcula el precio de venta necesario para obtener el margen deseado en ML."""
    # Tarifa total aproximada (comision + MP + IVA)
    total_fee_rate = (
        category_config["commission"] +
        category_config["mercado_pago"] +
        (category_config["commission"] + category_config["mercado_pago"]) * category_config["iva_on_fees"]
    )
    
    if category_config["shipping"] == "free":
        # Necesitamos cubrir el envío
        # Precio = (Costo + Envío) / (1 - margen - tarifa)
        denominator = 1 - target_margin - total_fee_rate
        if denominator <= 0:
            return None
        price = (cost + shipping_cost) / denominator
    else:
        denominator = 1 - target_margin - total_fee_rate
        if denominator <= 0:
            return None
        price = cost / denominator
    
    return round(price, 2)

def calculate_ml_with_discount(cost, base_price, discount_pct, category_config, shipping_cost=0):
    """Calcula métricas cuando se aplica un descuento al precio base."""
    discounted_price = round(base_price * (1 - discount_pct), 2)
    fees = calculate_ml_fees(discounted_price, category_config, shipping_cost)
    
    profit = discounted_price - cost - fees["total_fees"]
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
    }

# ============================================================
# FUNCIONES DE CÁLCULO — AMAZON
# ============================================================
def calculate_amazon_fees(price, category_config, fba_fee=0, shipping_cost=0):
    """Calcula todas las comisiones de Amazon para un precio dado."""
    referral = price * category_config["referral"]
    closing = category_config["closing"]  # Fixed fee per unit for some categories
    fba = fba_fee if fba_fee else 0
    shipping = shipping_cost if not fba_fee else 0  # If FBA, no shipping cost to seller
    
    total_fees = referral + closing + fba + shipping
    
    return {
        "referral": referral,
        "closing": closing,
        "fba": fba,
        "shipping": shipping,
        "total_fees": total_fees,
    }

def calculate_amazon_price(cost, target_margin, category_config, fba_fee=0, shipping_cost=0):
    """Calcula el precio de venta necesario para obtener el margen deseado en Amazon."""
    # Tarifa total aproximada
    total_fee_rate = category_config["referral"]
    fixed_fees = category_config["closing"] + fba_fee + (shipping_cost if not fba_fee else 0)
    
    # Precio = (Costo + FixedFees) / (1 - margen - referral_rate)
    denominator = 1 - target_margin - total_fee_rate
    if denominator <= 0:
        return None
    price = (cost + fixed_fees) / denominator
    
    return round(price, 2)

def calculate_amazon_with_discount(cost, base_price, discount_pct, category_config, fba_fee=0, shipping_cost=0):
    """Calcula métricas cuando se aplica un descuento al precio base en Amazon."""
    discounted_price = round(base_price * (1 - discount_pct), 2)
    fees = calculate_amazon_fees(discounted_price, category_config, fba_fee, shipping_cost)
    
    profit = discounted_price - cost - fees["total_fees"]
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
    }

# ============================================================
# SIDEBAR — CONFIGURACIÓN GLOBAL
# ============================================================
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    
    st.markdown("---")
    st.markdown("#### 💰 Moneda")
    currency = st.selectbox("Moneda", ["MXN", "USD", "COP", "ARS"], index=0)
    
    st.markdown("---")
    st.markdown("#### 📦 Envío")
    
    shipping_mode = st.radio(
        "Modo de envío Mercado Libre",
        ["Mercado Envíos (Gratis para el comprador)", "El comprador paga envío"],
        index=0
    )
    ml_shipping_cost = st.number_input(
        f"Costo de envío promedio ({currency})",
        value=80.0 if currency == "MXN" else 5.0,
        min_value=0.0,
        step=10.0 if currency == "MXN" else 1.0
    )
    
    st.markdown("---")
    st.markdown("#### 🚚 Amazon FBA")
    use_fba = st.checkbox("Usar Amazon FBA", value=False)
    fba_cost_per_unit = st.number_input(
        f"Costo FBA por unidad ({currency})",
        value=0.0,
        min_value=0.0,
        step=5.0 if currency == "MXN" else 0.5,
        disabled=not use_fba
    )
    amazon_shipping = st.number_input(
        f"Costo de envío (FBM) por unidad ({currency})",
        value=40.0 if currency == "MXN" else 3.0,
        min_value=0.0,
        step=10.0 if currency == "MXN" else 1.0,
        disabled=use_fba
    )

# ============================================================
# HEADER PRINCIPAL
# ============================================================
st.markdown('<div class="main-header">💰 Marketplace Pricing Calculator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Calcula precios óptimos con comisiones y descuentos para Mercado Libre y Amazon</div>', unsafe_allow_html=True)

# ============================================================
# TABS PRINCIPALES
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "🧮 Calculadora Manual",
    "📊 Comparador Marketplaces",
    "📁 Importar Productos"
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
            f"💵 Costo del producto ({currency})",
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
        st.markdown("#### 🏷️ Descuentos a evaluar")
        discount_levels = st.multiselect(
            "Niveles de descuento a calcular",
            ["5%", "10%", "15%", "20%", "25%", "30%", "40%", "50%"],
            default=["10%", "20%", "30%"]
        )
        discount_levels = [int(d.replace("%", "")) / 100 for d in discount_levels]
    
    st.markdown("---")
    
    # Mercado Libre Section
    st.markdown("### 🟡 Mercado Libre")
    
    ml_col1, ml_col2 = st.columns(2)
    
    with ml_col1:
        ml_category = st.selectbox(
            "Categoría ML",
            list(ML_CATEGORIES.keys()),
            key="ml_cat_manual"
        )
        ml_config = ML_CATEGORIES[ml_category].copy()
        if shipping_mode == "El comprador paga envío":
            ml_config["shipping"] = "buyer_pays"
    
    with ml_col2:
        if ml_category == "Custom":
            ml_custom_commission = st.number_input("Comisión ML (%)", value=15.0, min_value=0.0, max_value=50.0) / 100
            ml_config["commission"] = ml_custom_commission
    
    # Calculate ML
    ml_base_price = calculate_ml_price(cost, target_margin, ml_config, ml_shipping_cost)
    
    if ml_base_price:
        ml_fees = calculate_ml_fees(ml_base_price, ml_config, ml_shipping_cost)
        ml_profit = ml_base_price - cost - ml_fees["total_fees"]
        ml_profit_margin = (ml_profit / ml_base_price) * 100
        
        # Display base metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base ML</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${ml_base_price:,.2f} {currency}</div>
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
                    <b>Comisión ML ({ml_config['commission']*100:.0f}%):</b> ${ml_fees['commission']:,.2f}<br>
                    <b>Mercado Pago ({ml_config['mercado_pago']*100:.2f}%):</b> ${ml_fees['mercado_pago']:,.2f}<br>
                    <b>IVA sobre comisiones ({ml_config['iva_on_fees']*100:.0f}%):</b> ${ml_fees['iva_on_fees']:,.2f}<br>
                </div>
                """, unsafe_allow_html=True)
            with fee_col2:
                if ml_fees["shipping"] > 0:
                    st.markdown(f"""
                    <div class="fee-breakdown">
                        <b>Envío (gratis):</b> ${ml_fees['shipping']:,.2f}<br>
                        <b>Total comisiones:</b> ${ml_fees['total_fees']:,.2f}<br>
                        <b>% del precio:</b> {(ml_fees['total_fees']/ml_base_price)*100:.1f}%
                    </div>
                    """, unsafe_allow_html=True)
        
        # Discount scenarios
        if discount_levels:
            st.markdown("#### 🏷️ Escenarios con Descuento")
            
            discount_data = []
            for d_pct in discount_levels:
                result = calculate_ml_with_discount(cost, ml_base_price, d_pct, ml_config, ml_shipping_cost)
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
            
            # Warning for unprofitable discounts
            for d in discount_data:
                if d["profit"] < 0:
                    st.error(f"⚠️ Con {d['discount_pct']:.0f}% de descuento **PIERDES** ${abs(d['profit']):,.2f} por unidad. ¡No recomendado!")
                elif d["profit_margin"] < 10:
                    st.warning(f"⚠️ Con {d['discount_pct']:.0f}% de descuento tu margen es solo {d['profit_margin']:.1f}%. Margen bajo.")
    else:
        st.error("❌ El margen deseado + comisiones superan el 100%. Reduce el margen o verifica las comisiones.")
    
    st.markdown("---")
    
    # Amazon Section
    st.markdown("### 🟠 Amazon")
    
    az_col1, az_col2 = st.columns(2)
    
    with az_col1:
        az_category = st.selectbox(
            "Categoría Amazon",
            list(AMAZON_CATEGORIES.keys()),
            key="az_cat_manual"
        )
        az_config = AMAZON_CATEGORIES[az_category].copy()
    
    with az_col2:
        if az_category == "Custom":
            az_custom_referral = st.number_input("Referral Fee (%)", value=15.0, min_value=0.0, max_value=50.0) / 100
            az_config["referral"] = az_custom_referral
    
    # Calculate Amazon
    az_fba = fba_cost_per_unit if use_fba else 0
    az_ship = 0 if use_fba else amazon_shipping
    az_base_price = calculate_amazon_price(cost, target_margin, az_config, az_fba, az_ship)
    
    if az_base_price:
        az_fees = calculate_amazon_fees(az_base_price, az_config, az_fba, az_ship)
        az_profit = az_base_price - cost - az_fees["total_fees"]
        az_profit_margin = (az_profit / az_base_price) * 100
        
        # Display base metrics
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Amazon</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${az_base_price:,.2f} {currency}</div>
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
        
        # Fee breakdown
        with st.expander("📋 Desglose de comisiones Amazon"):
            fee_col1, fee_col2 = st.columns(2)
            with fee_col1:
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>Referral Fee ({az_config['referral']*100:.0f}%):</b> ${az_fees['referral']:,.2f}<br>
                    <b>Closing Fee:</b> ${az_fees['closing']:,.2f}<br>
                    <b>FBA:</b> ${az_fees['fba']:,.2f}<br>
                </div>
                """, unsafe_allow_html=True)
            with fee_col2:
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>Shipping:</b> ${az_fees['shipping']:,.2f}<br>
                    <b>Total comisiones:</b> ${az_fees['total_fees']:,.2f}<br>
                    <b>% del precio:</b> {(az_fees['total_fees']/az_base_price)*100:.1f}%
                </div>
                """, unsafe_allow_html=True)
        
        # Discount scenarios
        if discount_levels:
            st.markdown("#### 🏷️ Escenarios con Descuento")
            
            az_discount_data = []
            for d_pct in discount_levels:
                result = calculate_amazon_with_discount(cost, az_base_price, d_pct, az_config, az_fba, az_ship)
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
# TAB 2: COMPARADOR DE MARKETPLACES
# ============================================================
with tab2:
    st.markdown("### 📊 Comparador de Marketplaces")
    st.markdown("Compara el mismo producto en Mercado Libre y Amazon lado a lado.")
    
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    
    with comp_col1:
        comp_cost = st.number_input(f"💵 Costo ({currency})", value=150.0, min_value=0.0, step=10.0, key="comp_cost")
        comp_margin = st.slider("🎯 Margen deseado (%)", 0, 80, 30, key="comp_margin") / 100
    
    with comp_col2:
        comp_ml_cat = st.selectbox("Categoría ML", list(ML_CATEGORIES.keys()), key="comp_ml_cat")
        comp_ml_config = ML_CATEGORIES[comp_ml_cat].copy()
        if shipping_mode == "El comprador paga envío":
            comp_ml_config["shipping"] = "buyer_pays"
    
    with comp_col3:
        comp_az_cat = st.selectbox("Categoría Amazon", list(AMAZON_CATEGORIES.keys()), key="comp_az_cat")
        comp_az_config = AMAZON_CATEGORIES[comp_az_cat].copy()
    
    comp_az_fba = fba_cost_per_unit if use_fba else 0
    comp_az_ship = 0 if use_fba else amazon_shipping
    
    # Calculate both
    comp_ml_price = calculate_ml_price(comp_cost, comp_margin, comp_ml_config, ml_shipping_cost)
    comp_az_price = calculate_amazon_price(comp_cost, comp_margin, comp_az_config, comp_az_fba, comp_az_ship)
    
    if comp_ml_price and comp_az_price:
        comp_ml_fees = calculate_ml_fees(comp_ml_price, comp_ml_config, ml_shipping_cost)
        comp_az_fees = calculate_amazon_fees(comp_az_price, comp_az_config, comp_az_fba, comp_az_ship)
        
        comp_ml_profit = comp_ml_price - comp_cost - comp_ml_fees["total_fees"]
        comp_az_profit = comp_az_price - comp_cost - comp_az_fees["total_fees"]
        
        comp_ml_margin = (comp_ml_profit / comp_ml_price) * 100
        comp_az_margin = (comp_az_profit / comp_az_price) * 100
        
        st.markdown("---")
        
        # Side by side comparison
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 🟡 Mercado Libre")
            st.markdown(f'''
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Recomendado</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_ml_price:,.2f} {currency}</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Ganancia neta:** ${comp_ml_profit:,.2f} ({comp_ml_margin:.1f}%)
            - **Comisiones totales:** ${comp_ml_fees['total_fees']:,.2f} ({(comp_ml_fees['total_fees']/comp_ml_price)*100:.1f}%)
            - **Comisión ML:** {comp_ml_config['commission']*100:.0f}%
            - **Mercado Pago:** {comp_ml_config['mercado_pago']*100:.2f}%
            - **Envío:** {'Gratis (vendedor paga)' if comp_ml_config['shipping'] == 'free' else 'Comprador paga'}
            """)
            
            # Profit margin at different discounts
            st.markdown("**Margen con descuentos:**")
            for d in [10, 20, 30]:
                d_result = calculate_ml_with_discount(comp_cost, comp_ml_price, d/100, comp_ml_config, ml_shipping_cost)
                color = "profit-positive" if d_result["profit"] > 0 else "profit-negative"
                st.markdown(f"- Con **{d}% descuento**: <span class='{color}'>${d_result['discounted_price']:,.2f}</span> → Ganancia: <span class='{color}'>${d_result['profit']:,.2f} ({d_result['profit_margin']:.1f}%)</span>", unsafe_allow_html=True)
        
        with c2:
            st.markdown("#### 🟠 Amazon")
            st.markdown(f'''
                <div class="metric-card-orange">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Precio Recomendado</div>
                    <div style="font-size: 2rem; font-weight: 700;">${comp_az_price:,.2f} {currency}</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown(f"""
            - **Ganancia neta:** ${comp_az_profit:,.2f} ({comp_az_margin:.1f}%)
            - **Comisiones totales:** ${comp_az_fees['total_fees']:,.2f} ({(comp_az_fees['total_fees']/comp_az_price)*100:.1f}%)
            - **Referral Fee:** {comp_az_config['referral']*100:.0f}%
            - **FBA:** {'Sí ($' + f'{comp_az_fba:,.2f}' + ')' if use_fba else 'No (FBM)'}
            - **Envío:** {'Incluido en FBA' if use_fba else 'Vendedor paga'}
            """)
            
            # Profit margin at different discounts
            st.markdown("**Margen con descuentos:**")
            for d in [10, 20, 30]:
                d_result = calculate_amazon_with_discount(comp_cost, comp_az_price, d/100, comp_az_config, comp_az_fba, comp_az_ship)
                color = "profit-positive" if d_result["profit"] > 0 else "profit-negative"
                st.markdown(f"- Con **{d}% descuento**: <span class='{color}'>${d_result['discounted_price']:,.2f}</span> → Ganancia: <span class='{color}'>${d_result['profit']:,.2f} ({d_result['profit_margin']:.1f}%)</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Recommendation
        if comp_ml_price < comp_az_price:
            diff = comp_az_price - comp_ml_price
            st.info(f"💡 **Mercado Libre permite un precio ${diff:,.2f} más bajo** que Amazon para el mismo margen. Esto puede ser una ventaja competitiva en ML.")
        else:
            diff = comp_ml_price - comp_az_price
            st.info(f"💡 **Amazon permite un precio ${diff:,.2f} más bajo** que Mercado Libre para el mismo margen. Amazon puede ser más competitivo en precio.")
        
        if comp_ml_profit > comp_az_profit:
            st.success(f"✅ **Mercado Libre es más rentable** por ${comp_ml_profit - comp_az_profit:,.2f} por unidad.")
        else:
            st.success(f"✅ **Amazon es más rentable** por ${comp_az_profit - comp_ml_profit:,.2f} por unidad.")
    
    else:
        st.error("❌ No se puede calcular. El margen + comisiones superan el 100%.")

# ============================================================
# TAB 3: IMPORTAR PRODUCTOS (CSV/Excel)
# ============================================================
with tab3:
    st.markdown("### 📁 Importar Productos desde CSV/Excel")
    st.markdown("Sube un archivo con tus productos y calcula precios para todos a la vez.")
    
    st.markdown("""
    **Formato esperado:**
    - `sku` — Código del producto
    - `nombre` — Nombre del producto
    - `costo` — Costo unitario
    - `categoria_ml` (opcional) — Categoría para Mercado Libre
    - `categoria_amazon` (opcional) — Categoría para Amazon
    """)
    
    uploaded_file = st.file_uploader("Sube CSV o Excel", type=["csv", "xlsx", "xls"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_products = pd.read_csv(uploaded_file)
            else:
                df_products = pd.read_excel(uploaded_file)
            
            st.success(f"✅ {len(df_products)} productos cargados")
            st.dataframe(df_products.head(10), use_container_width=True)
            
            # Required columns check
            required = ['sku', 'nombre', 'costo']
            missing = [c for c in required if c not in df_products.columns]
            if missing:
                st.error(f"❌ Columnas faltantes: {', '.join(missing)}")
            else:
                # Configuration for bulk calculation
                st.markdown("---")
                st.markdown("#### ⚙️ Configuración para todos los productos")
                
                bulk_margin = st.slider("Margen deseado (%)", 0, 80, 30, key="bulk_margin") / 100
                bulk_discounts = st.multiselect(
                    "Descuentos a calcular",
                    [5, 10, 15, 20, 25, 30, 40, 50],
                    default=[10, 20, 30],
                    key="bulk_discounts"
                )
                
                default_ml_cat = st.selectbox("Categoría ML por defecto", list(ML_CATEGORIES.keys()), key="bulk_ml_cat")
                default_az_cat = st.selectbox("Categoría Amazon por defecto", list(AMAZON_CATEGORIES.keys()), key="bulk_az_cat")
                
                if st.button("🚀 Calcular Precios para Todos", type="primary"):
                    with st.spinner("Calculando..."):
                        results = []
                        
                        for _, row in df_products.iterrows():
                            sku = row['sku']
                            nombre = row['nombre']
                            costo = float(row['costo'])
                            
                            # Get category (or default)
                            ml_cat = ML_CATEGORIES.get(row.get('categoria_ml', default_ml_cat), ML_CATEGORIES[default_ml_cat])
                            az_cat = AMAZON_CATEGORIES.get(row.get('categoria_amazon', default_az_cat), AMAZON_CATEGORIES[default_az_cat])
                            
                            # ML
                            ml_price = calculate_ml_price(costo, bulk_margin, ml_cat, ml_shipping_cost)
                            ml_profit = ml_price - costo - calculate_ml_fees(ml_price, ml_cat, ml_shipping_cost)["total_fees"] if ml_price else 0
                            
                            # Amazon
                            az_fba = fba_cost_per_unit if use_fba else 0
                            az_ship = 0 if use_fba else amazon_shipping
                            az_price = calculate_amazon_price(costo, bulk_margin, az_cat, az_fba, az_ship)
                            az_profit = az_price - costo - calculate_amazon_fees(az_price, az_cat, az_fba, az_ship)["total_fees"] if az_price else 0
                            
                            result_row = {
                                "SKU": sku,
                                "Producto": nombre,
                                "Costo": costo,
                                "ML Precio": ml_price if ml_price else 0,
                                "ML Ganancia": round(ml_profit, 2),
                                "ML Margen": round((ml_profit/ml_price)*100, 1) if ml_price else 0,
                                "Amazon Precio": az_price if az_price else 0,
                                "Amazon Ganancia": round(az_profit, 2),
                                "Amazon Margen": round((az_profit/az_price)*100, 1) if az_price else 0,
                            }
                            
                            # Discounts
                            for d in bulk_discounts:
                                if ml_price:
                                    ml_d = calculate_ml_with_discount(costo, ml_price, d/100, ml_cat, ml_shipping_cost)
                                    result_row[f"ML -{d}%"] = ml_d['discounted_price']
                                    result_row[f"ML -{d}% Ganancia"] = ml_d['profit']
                                    result_row[f"ML -{d}% Margen"] = ml_d['profit_margin']
                                
                                if az_price:
                                    az_d = calculate_amazon_with_discount(costo, az_price, d/100, az_cat, az_fba, az_ship)
                                    result_row[f"AZ -{d}%"] = az_d['discounted_price']
                                    result_row[f"AZ -{d}% Ganancia"] = az_d['profit']
                                    result_row[f"AZ -{d}% Margen"] = az_d['profit_margin']
                            
                            results.append(result_row)
                        
                        df_results = pd.DataFrame(results)
                        st.success(f"✅ Cálculo completado para {len(results)} productos")
                        st.dataframe(df_results, use_container_width=True)
                        
                        # Download
                        csv_buffer = io.StringIO()
                        df_results.to_csv(csv_buffer, index=False)
                        st.download_button(
                            "📥 Descargar Resultados CSV",
                            csv_buffer.getvalue(),
                            f"precios_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv"
                        )
                        
                        # Excel
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df_results.to_excel(writer, index=False, sheet_name='Precios')
                        st.download_button(
                            "📥 Descargar Resultados Excel",
                            excel_buffer.getvalue(),
                            f"precios_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
        
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
    f"Marketplace Pricing Calculator • Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    f"</div>",
    unsafe_allow_html=True
)
