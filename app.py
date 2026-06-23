#!/usr/bin/env python3
"""
Calculadora de Precios para Marketplaces — México 2026
Mercado Libre y Amazon México con comisiones reales 2026
Lógica: Precio tope calculado para 5% de ganancia con 60% descuento
Desde ese precio base fijo, se calculan las ganancias con 60%, 50%, 40%, 30% OFF
Sincronización con Shopify morekashop1 para obtener costos
"""

import streamlit as st
import pandas as pd
import requests
import time
import io
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIGURACIÓN GOOGLE SHEETS — PESOS Y MEDIDAS
# ============================================================
GSHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
PESOS_MEDIDAS_SHEET_ID = "1ZiqaICBBQ68lYlLG5Xx9oCPyHwruOHLDrR_TNYt3Sjg"

def get_gsheets_credentials():
    """Obtiene credenciales de Google Sheets desde secrets o archivo"""
    try:
        creds_dict = st.secrets.get("google_sheets", {})
        if creds_dict:
            return Credentials.from_service_account_info(creds_dict, scopes=GSHEETS_SCOPES)
    except:
        pass
    
    creds_path = "/root/.openclaw/workspace/pesos-medidas-moreka/pesos-y-medidas-credentials.json"
    if os.path.exists(creds_path):
        return Credentials.from_service_account_file(creds_path, scopes=GSHEETS_SCOPES)
    
    return None

@st.cache_data(ttl=300)
def fetch_pesos_medidas():
    """Lee datos de pesos y medidas desde Google Sheets"""
    try:
        creds = get_gsheets_credentials()
        if not creds:
            return None, "Credenciales de Google Sheets no configuradas"
        
        client = gspread.authorize(creds)
        sh = client.open_by_key(PESOS_MEDIDAS_SHEET_ID)
        worksheet = sh.sheet1
        values = worksheet.get_all_values()
        
        if not values or len(values) < 2:
            return None, "Hoja vacía"
        
        headers = values[0]
        headers = ['SKU' if h == '.' else h for h in headers]
        headers = [h if h else f"Col_{i}" for i, h in enumerate(headers)]
        
        records = []
        for row in values[1:]:
            if not any(cell.strip() for cell in row):
                continue
            record = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            records.append(record)
        
        return records, None
    except Exception as e:
        return None, str(e)

def get_product_dimensions(sku, modelo, pesos_medidas_data):
    """Busca pesos y medidas por SKU o modelo"""
    if not pesos_medidas_data:
        return None
    
    sku_lower = str(sku).strip().lower() if sku else ""
    modelo_lower = str(modelo).strip().lower() if modelo else ""
    
    for record in pesos_medidas_data:
        record_sku = str(record.get('SKU', '')).strip().lower()
        record_modelo = str(record.get('Modelo', '')).strip().lower()
        
        if (sku_lower and record_sku == sku_lower) or (modelo_lower and record_modelo == modelo_lower):
            return {
                'sku': record.get('SKU', ''),
                'modelo': record.get('Modelo', ''),
                'titulo': record.get('Titutlo', ''),
                'ancho_cm': parse_float(record.get('Ancho cm', 0)),
                'largo_cm': parse_float(record.get('Largo cm', 0)),
                'profundidad_cm': parse_float(record.get('Profundidad cm', 0)),
                'peso_kg': parse_float(record.get('Peso (kg)', 0)),
                'largo_caja_cm': parse_float(record.get('Largo caja cm', 0)),
                'ancho_caja_cm': parse_float(record.get('Ancho caja cm', 0)),
                'profundidad_caja_cm': parse_float(record.get('Profundidad caja cm', 0)),
                'peso_caja_kg': parse_float(record.get('Pesos caja (kg)', 0)),
                'peso_volumetrico': parse_float(record.get('Peso Volumétrico (kg)', 0)),
            }
    
    return None

def parse_float(value, default=0.0):
    """Convierte valor a float, maneja comas como decimales"""
    if not value:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(',', '.').replace(' ', '').strip()
        return float(value)
    except (ValueError, TypeError):
        return default

def calculate_volumetric_weight(largo, ancho, profundidad):
    """Calcula peso volumétrico: largo × ancho × alto / 5000 (kg)"""
    if largo > 0 and ancho > 0 and profundidad > 0:
        return (largo * ancho * profundidad) / 5000
    return 0

def get_billable_weight(peso_real, largo, ancho, profundidad):
    """Peso facturable: el mayor entre peso real y volumétrico"""
    peso_volumetrico = calculate_volumetric_weight(largo, ancho, profundidad)
    return max(peso_real, peso_volumetrico)

# ============================================================
# TARIFAS DE ENVÍO MERCADO LIBRE MÉXICO — ABRIL 2026
# Productos < $299: costo variable por peso
# ============================================================
def get_ml_shipping_cost(price, peso_kg, largo, ancho, profundidad):
    """
    Calcula costo de envío de Mercado Libre México basado en peso y dimensiones.
    Desde abril 2026: productos < $299 usan tarifa variable por peso.
    Productos >= $299: envío gratis (ML cubre parcialmente según reputación).
    """
    if price >= 299:
        # Envío gratis: ML cubre parte, vendedor paga el resto
        # Aproximación: vendedor paga ~50% del costo real
        billable_weight = get_billable_weight(peso_kg, largo, ancho, profundidad)
        return calculate_ml_shipping_table(billable_weight, price) * 0.5
    
    billable_weight = get_billable_weight(peso_kg, largo, ancho, profundidad)
    return calculate_ml_shipping_table(billable_weight, price)

def calculate_ml_shipping_table(peso_kg, price):
    """Tabla de costos de envío ML México — Abril 2026"""
    
    # Determinar rango de precio
    if price < 99:
        price_range = "low"
    elif price < 199:
        price_range = "mid"
    elif price < 299:
        price_range = "high"
    else:
        price_range = "free"
    
    # Tabla de costos por peso (MXN)
    # Fuente: Mercado Libre México — Abril 2026
    shipping_table = {
        "low": {   # $0 - $98.99
            0.3: 25, 0.5: 28.50, 1.0: 33, 2.0: 35, 3.0: 37, 4.0: 39,
            5.0: 40, 7.0: 45, 9.0: 51, 12.0: 59, 15.0: 69, 20.0: 81,
            30.0: 102, 40.0: 126, 50.0: 163, 60.0: 183
        },
        "mid": {   # $99 - $198.99
            0.3: 32, 0.5: 34, 1.0: 38, 2.0: 40, 3.0: 46, 4.0: 50,
            5.0: 53, 7.0: 59, 9.0: 67, 12.0: 78, 15.0: 92, 20.0: 108,
            30.0: 137, 40.0: 170, 50.0: 220, 60.0: 247
        },
        "high": {  # $199 - $298.99
            0.3: 35, 0.5: 38, 1.0: 39, 2.0: 41, 3.0: 48, 4.0: 54,
            5.0: 59, 7.0: 70, 9.0: 81, 12.0: 96, 15.0: 113, 20.0: 140,
            30.0: 195, 40.0: 250, 50.0: 305, 60.0: 334
        },
        "free": {  # >= $299 (envío gratis — vendedor paga 50% aprox)
            0.3: 26.20, 0.5: 28, 1.0: 29.80, 2.0: 33.80, 3.0: 38,
            5.0: 44, 7.0: 49, 9.0: 55.80, 12.0: 64.60, 15.0: 76,
            20.0: 89, 30.0: 112.60
        }
    }
    
    table = shipping_table.get(price_range, shipping_table["low"])
    
    # Encontrar el rango de peso correspondiente
    pesos = sorted(table.keys())
    for i, p in enumerate(pesos):
        if peso_kg <= p:
            return table[p]
    
    # Si supera el máximo, usar extrapolación
    return table[pesos[-1]] + (peso_kg - pesos[-1]) * 5

# ============================================================
# TARIFAS FBA AMAZON MÉXICO — 2026
# Basadas en tamaño tier y peso
# ============================================================
def get_amazon_fba_fee(peso_kg, largo_cm, ancho_cm, profundidad_cm):
    """
    Calcula tarifa FBA de Amazon México basada en tamaño y peso.
    Usa peso real o volumétrico (el mayor).
    """
    # Convertir dimensiones a pulgadas para comparar
    largo_in = largo_cm / 2.54
    ancho_in = ancho_cm / 2.54
    profundidad_in = profundidad_cm / 2.54
    peso_lb = peso_kg * 2.20462
    
    # Peso volumétrico en kg
    peso_volumetrico_kg = calculate_volumetric_weight(largo_cm, ancho_cm, profundidad_cm)
    billable_weight_kg = max(peso_kg, peso_volumetrico_kg)
    billable_weight_lb = billable_weight_kg * 2.20462
    
    # Determinar size tier
    # Small Standard: max 15" x 12" x 0.75", up to 12 oz (0.34 kg)
    # Large Standard: max 18" x 14" x 8", up to 20 lbs (9.07 kg)
    # Large Bulky: 21-50 lbs, max 59" longest side, 130" perimeter
    # Extra-Large: 51-70 lbs
    
    max_dimension = max(largo_in, ancho_in, profundidad_in) if any([largo_in, ancho_in, profundidad_in]) else 0
    perimeter = largo_in + ancho_in + profundidad_in if all([largo_in, ancho_in, profundidad_in]) else 0
    
    # Tarifas FBA México 2026 (aproximadas en MXN, basadas en US fees convertidos)
    # Small Standard
    if max_dimension <= 15 and max(largo_in, ancho_in) <= 12 and profundidad_in <= 0.75 and billable_weight_lb <= 0.75:
        if billable_weight_lb <= 0.25:
            return 58.0  # ~$3.06 USD
        elif billable_weight_lb <= 0.5:
            return 61.0  # ~$3.22 USD
        else:
            return 65.0  # ~$3.44 USD
    
    # Large Standard
    if max_dimension <= 18 and max(largo_in, ancho_in) <= 14 and profundidad_in <= 8 and billable_weight_lb <= 20:
        if billable_weight_lb <= 0.25:
            return 73.0   # ~$3.86 USD
        elif billable_weight_lb <= 0.5:
            return 77.0   # ~$4.08 USD
        elif billable_weight_lb <= 0.75:
            return 81.0   # ~$4.28 USD
        elif billable_weight_lb <= 1.0:
            return 88.0   # ~$4.65 USD
        elif billable_weight_lb <= 1.5:
            return 104.0  # ~$5.50 USD
        elif billable_weight_lb <= 2.0:
            return 115.0  # ~$6.10 USD
        elif billable_weight_lb <= 2.5:
            return 121.0  # ~$6.39 USD
        elif billable_weight_lb <= 3.0:
            return 128.0  # ~$6.75 USD
        else:
            # +$0.16 per half-pound above 3 lbs
            extra_half_pounds = max(0, (billable_weight_lb - 3.0) / 0.5)
            return 128.0 + (extra_half_pounds * 3.0)
    
    # Large Bulky (21-50 lbs)
    if billable_weight_lb <= 50 and max_dimension <= 59 and perimeter <= 130:
        base = 184.0  # ~$9.73 USD
        extra = max(0, billable_weight_lb - 2.0) * 8.0  # ~$0.42/lb
        return base + extra
    
    # Extra-Large (51-70 lbs)
    if billable_weight_lb <= 70:
        base = 477.0  # ~$25.21 USD
        extra = max(0, billable_weight_lb - 51.0) * 8.0  # ~$0.42/lb
        return base + extra
    
    # Special Oversize (70+ lbs)
    base = 2597.0  # ~$137.32 USD
    extra = max(0, billable_weight_lb - 90.0) * 15.0  # ~$0.79/lb
    return base + extra

def get_amazon_size_tier(largo_cm, ancho_cm, profundidad_cm, peso_kg):
    """Determina el tier de tamaño de Amazon basado en dimensiones y peso"""
    largo_in = largo_cm / 2.54
    ancho_in = ancho_cm / 2.54
    profundidad_in = profundidad_cm / 2.54
    peso_lb = peso_kg * 2.20462
    
    max_dimension = max(largo_in, ancho_in, profundidad_in) if any([largo_in, ancho_in, profundidad_in]) else 0
    perimeter = largo_in + ancho_in + profundidad_in if all([largo_in, ancho_in, profundidad_in]) else 0
    
    if max_dimension <= 15 and max(largo_in, ancho_in) <= 12 and profundidad_in <= 0.75 and peso_lb <= 0.75:
        return "Small Standard"
    elif max_dimension <= 18 and max(largo_in, ancho_in) <= 14 and profundidad_in <= 8 and peso_lb <= 20:
        return "Large Standard"
    elif peso_lb <= 50 and max_dimension <= 59 and perimeter <= 130:
        return "Large Bulky"
    elif peso_lb <= 70:
        return "Extra-Large"
    else:
        return "Special Oversize"

def get_amazon_fbm_shipping(peso_kg, largo_cm, ancho_cm, profundidad_cm):
    """Costo aproximado de envío FBM (vendedor envía)"""
    # Tarifas aproximadas de paquetería México 2026
    billable_weight = get_billable_weight(peso_kg, largo_cm, ancho_cm, profundidad_cm)
    
    if billable_weight <= 0.5:
        return 50.0
    elif billable_weight <= 1.0:
        return 70.0
    elif billable_weight <= 2.0:
        return 90.0
    elif billable_weight <= 3.0:
        return 110.0
    elif billable_weight <= 5.0:
        return 140.0
    elif billable_weight <= 10.0:
        return 200.0
    elif billable_weight <= 20.0:
        return 300.0
    else:
        return 400.0 + (billable_weight - 20.0) * 15

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
    .metric-card-dark {
        background: linear-gradient(135deg, #232526 0%, #414345 100%);
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
    .scenario-card {
        background: #ffffff;
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .scenario-card.best {
        border-color: #f5af19;
        background: #fffbf0;
    }
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

def calculate_ml_base_price(cost, target_margin, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0, ad_cost_pct=0.10, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0):
    """Calcula el precio BASE necesario para que el precio con descuento mantenga el margen deseado.
    Incluye costo de publicidad como % del precio de venta y envío basado en peso/dimensiones."""
    
    price_discounted = cost * 2.5  # Estimación inicial
    
    for _ in range(30):
        ad_cost = price_discounted * ad_cost_pct
        
        # Calcular envío basado en peso y dimensiones
        if peso_kg > 0:
            shipping = get_ml_shipping_cost(price_discounted, peso_kg, largo_cm, ancho_cm, profundidad_cm)
        else:
            shipping = shipping_cost
        
        total_cost = cost + ad_cost + shipping
        
        fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
        total_fees = fees["total_fees"]
        
        new_price_discounted = (total_cost + total_fees) / (1 - target_margin)
        
        if abs(new_price_discounted - price_discounted) < 0.01:
            break
        price_discounted = new_price_discounted
    
    price_base = price_discounted / (1 - discount_pct)
    
    return round(price_base, 2), round(price_discounted, 2)

def calculate_ml_from_fixed_base(cost, base_price, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0, ad_cost_pct=0.10, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0):
    """Desde un precio base FIJO, calcula ganancia con un % de descuento dado. Incluye publicidad y envío por peso."""
    price_discounted = base_price * (1 - discount_pct)
    
    ad_cost = price_discounted * ad_cost_pct
    
    # Calcular envío basado en peso y dimensiones
    if peso_kg > 0:
        shipping = get_ml_shipping_cost(price_discounted, peso_kg, largo_cm, ancho_cm, profundidad_cm)
    else:
        shipping = shipping_cost
    
    total_cost = cost + ad_cost + shipping
    
    fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
    total_fees = fees["total_fees"]
    
    profit = price_discounted - total_cost - total_fees
    margin = (profit / price_discounted) * 100 if price_discounted > 0 else 0
    roi = (profit / cost) * 100 if cost > 0 else 0
    
    return {
        "discount_pct": discount_pct * 100,
        "base_price": base_price,
        "discounted_price": round(price_discounted, 2),
        "discount_amount": round(base_price - price_discounted, 2),
        "product_cost": cost,
        "ad_cost": round(ad_cost, 2),
        "shipping_cost": round(shipping, 2),
        "total_cost": round(total_cost, 2),
        "fees": fees,
        "profit": round(profit, 2),
        "margin": round(margin, 2),
        "roi": round(roi, 2),
    }

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

def calculate_amazon_base_price(cost, target_margin, discount_pct, category_name, fba_fee=0, shipping_cost=0, plan_professional=True, ad_cost_pct=0.10, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0, use_fba=False):
    """Calcula el precio BASE necesario para que el precio con descuento mantenga el margen deseado. Incluye publicidad y envío por peso/dimensiones."""
    
    price_discounted = cost * 2.5  # Estimación inicial
    
    for _ in range(30):
        ad_cost = price_discounted * ad_cost_pct
        
        # Calcular FBA fee basado en peso y dimensiones
        if use_fba and peso_kg > 0:
            fba = get_amazon_fba_fee(peso_kg, largo_cm, ancho_cm, profundidad_cm)
        else:
            fba = fba_fee
        
        # Calcular envío FBM basado en peso y dimensiones
        if not use_fba and peso_kg > 0:
            shipping = get_amazon_fbm_shipping(peso_kg, largo_cm, ancho_cm, profundidad_cm)
        else:
            shipping = shipping_cost
        
        total_cost = cost + ad_cost + shipping
        
        fees = calculate_amazon_fees(price_discounted, category_name, fba, 0, plan_professional)
        total_fees = fees["total_fees"]
        
        new_price_discounted = (total_cost + total_fees) / (1 - target_margin)
        
        if abs(new_price_discounted - price_discounted) < 0.01:
            break
        price_discounted = new_price_discounted
    
    price_base = price_discounted / (1 - discount_pct)
    
    return round(price_base, 2), round(price_discounted, 2)

def calculate_amazon_from_fixed_base(cost, base_price, discount_pct, category_name, fba_fee=0, shipping_cost=0, plan_professional=True, ad_cost_pct=0.10, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0, use_fba=False):
    """Desde un precio base FIJO, calcula ganancia con un % de descuento dado. Incluye publicidad y envío por peso."""
    price_discounted = base_price * (1 - discount_pct)
    
    ad_cost = price_discounted * ad_cost_pct
    
    # Calcular FBA fee basado en peso y dimensiones
    if use_fba and peso_kg > 0:
        fba = get_amazon_fba_fee(peso_kg, largo_cm, ancho_cm, profundidad_cm)
    else:
        fba = fba_fee
    
    # Calcular envío FBM basado en peso y dimensiones
    if not use_fba and peso_kg > 0:
        shipping = get_amazon_fbm_shipping(peso_kg, largo_cm, ancho_cm, profundidad_cm)
    else:
        shipping = shipping_cost
    
    total_cost = cost + ad_cost + shipping
    
    fees = calculate_amazon_fees(price_discounted, category_name, fba, 0, plan_professional)
    total_fees = fees["total_fees"]
    
    profit = price_discounted - total_cost - total_fees
    margin = (profit / price_discounted) * 100 if price_discounted > 0 else 0
    roi = (profit / cost) * 100 if cost > 0 else 0
    
    return {
        "discount_pct": discount_pct * 100,
        "base_price": base_price,
        "discounted_price": round(price_discounted, 2),
        "discount_amount": round(base_price - price_discounted, 2),
        "product_cost": cost,
        "ad_cost": round(ad_cost, 2),
        "shipping_cost": round(shipping, 2),
        "fba_cost": round(fba, 2),
        "total_cost": round(total_cost, 2),
        "fees": fees,
        "profit": round(profit, 2),
        "margin": round(margin, 2),
        "roi": round(roi, 2),
    }

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
        "Costo de envío promedio (MXN) — solo si no usas pesos/medidas",
        value=0.0,
        min_value=0.0,
        step=10.0,
        help="Dejar en 0 para calcular automáticamente por peso y medidas"
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
        "Costo FBA por unidad (MXN) — solo si no usas pesos/medidas",
        value=0.0,
        min_value=0.0,
        step=5.0,
        disabled=not use_fba,
        help="Dejar en 0 para calcular automáticamente por peso y medidas"
    )
    amazon_shipping = st.number_input(
        "Costo de envío FBM por unidad (MXN) — solo si no usas pesos/medidas",
        value=0.0,
        min_value=0.0,
        step=10.0,
        disabled=use_fba,
        help="Dejar en 0 para calcular automáticamente por peso y medidas"
    )
    
    st.markdown("---")
    st.markdown("#### 📏 Pesos y Medidas (Google Sheets)")
    
    # Cargar datos de pesos y medidas
    pesos_medidas_data, pesos_medidas_error = fetch_pesos_medidas()
    
    selected_product = None
    product_dimensions = None
    
    if pesos_medidas_data:
        st.success(f"✅ {len(pesos_medidas_data)} productos cargados")
        
        # Crear lista de productos para selección
        product_options = []
        product_map = {}
        for record in pesos_medidas_data:
            sku = str(record.get('SKU', '')).strip()
            modelo = str(record.get('Modelo', '')).strip()
            titulo = str(record.get('Titutlo', '')).strip()
            
            if sku or modelo:
                display = f"{sku} — {modelo}" if sku and modelo else (sku or modelo)
                if titulo:
                    display += f" ({titulo[:30]}...)" if len(titulo) > 30 else f" ({titulo})"
                product_options.append(display)
                product_map[display] = {'sku': sku, 'modelo': modelo}
        
        product_options = sorted(product_options)
        product_options.insert(0, "— Seleccionar producto —")
        
        selected_display = st.selectbox(
            "Seleccionar producto",
            product_options,
            index=0
        )
        
        if selected_display != "— Seleccionar producto —":
            selected_product = product_map[selected_display]
            product_dimensions = get_product_dimensions(
                selected_product['sku'], 
                selected_product['modelo'], 
                pesos_medidas_data
            )
            
            if product_dimensions:
                st.markdown("<div class='success-box'>📏 Producto encontrado</div>", unsafe_allow_html=True)
    else:
        if pesos_medidas_error:
            st.error(f"❌ Error: {pesos_medidas_error}")
        else:
            st.warning("⚠️ No se pudieron cargar datos de pesos y medidas")
    
    st.markdown("---")
    st.markdown("<div style='font-size: 0.8rem; color: #999;'>Comisiones actualizadas: Junio 2026<br>Fuente: SAT / ML / Amazon</div>", unsafe_allow_html=True)

# ============================================================
# HEADER PRINCIPAL
# ============================================================
st.markdown('<div class="main-header">💰 Marketplace Pricing Calculator México 2026</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Precio base tope con 5% ganancia al 60% OFF (incluye 10% publicidad) — Simula ganancias con 60%, 50%, 40%, 30% descuento</div>', unsafe_allow_html=True)

st.markdown("""
<div class="success-box">
    <b>💡 Cómo funciona:</b> La app calcula el <b>precio base tope</b> para que con <b>60% de descuento</b> obtengas <b>5% de ganancia</b>. 
    Incluye automáticamente un <b>10% de costo de publicidad</b> sobre el precio de venta. 
    Ese precio base es fijo. Luego simula cuánto ganarías si aplicas <b>60%, 50%, 40% o 30%</b> de descuento sobre ese mismo precio base.
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
        
        # Si hay producto seleccionado, mostrar sus datos
        if product_dimensions:
            st.markdown(f"""
            <div class="success-box">
                <b>📏 Producto seleccionado:</b> {product_dimensions['modelo'] or product_dimensions['sku']}<br>
                <b>SKU:</b> {product_dimensions['sku']}<br>
                <b>Peso:</b> {product_dimensions['peso_kg']:.2f} kg<br>
                <b>Dimensiones:</b> {product_dimensions['largo_cm']:.1f} × {product_dimensions['ancho_cm']:.1f} × {product_dimensions['profundidad_cm']:.1f} cm<br>
                <b>Peso Volumétrico:</b> {product_dimensions['peso_volumetrico']:.2f} kg<br>
                <b>Peso Facturable:</b> {get_billable_weight(product_dimensions['peso_kg'], product_dimensions['largo_cm'], product_dimensions['ancho_cm'], product_dimensions['profundidad_cm']):.2f} kg
            </div>
            """, unsafe_allow_html=True)
            
            # Mostrar datos de caja si existen
            if product_dimensions['peso_caja_kg'] > 0:
                st.markdown(f"""
                <div class="warning-box">
                    <b>📦 Caja:</b> {product_dimensions['largo_caja_cm']:.1f} × {product_dimensions['ancho_caja_cm']:.1f} × {product_dimensions['profundidad_caja_cm']:.1f} cm<br>
                    <b>Peso caja:</b> {product_dimensions['peso_caja_kg']:.2f} kg
                </div>
                """, unsafe_allow_html=True)
            
            product_name = st.text_input("Nombre del producto", value=product_dimensions['titulo'] or product_dimensions['modelo'] or "Ej: Audífonos Bluetooth NEBRO WE017")
        else:
            product_name = st.text_input("Nombre del producto", "Ej: Audífonos Bluetooth NEBRO WE017")
        
        cost = st.number_input(
            "💵 Costo del producto (MXN)",
            value=150.0,
            min_value=0.0,
            step=10.0
        )
        
        st.markdown("<div class='warning-box'>📌 El margen objetivo está fijado en <b>5% de ganancia</b> con <b>60% OFF</b>. Este es el precio tope.</div>", unsafe_allow_html=True)
        
        # Mostrar inputs de peso y medidas manuales (si no hay producto seleccionado)
        if not product_dimensions:
            st.markdown("---")
            st.markdown("#### 📏 Pesos y Medidas Manual")
            peso_manual = st.number_input("Peso (kg)", value=0.0, min_value=0.0, step=0.1)
            largo_manual = st.number_input("Largo (cm)", value=0.0, min_value=0.0, step=0.5)
            ancho_manual = st.number_input("Ancho (cm)", value=0.0, min_value=0.0, step=0.5)
            profundidad_manual = st.number_input("Profundidad/Alto (cm)", value=0.0, min_value=0.0, step=0.5)
        else:
            peso_manual = 0
            largo_manual = 0
            ancho_manual = 0
            profundidad_manual = 0
    
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
    
    # Determinar peso y dimensiones a usar
    if product_dimensions:
        peso_kg = product_dimensions['peso_kg']
        largo_cm = product_dimensions['largo_cm']
        ancho_cm = product_dimensions['ancho_cm']
        profundidad_cm = product_dimensions['profundidad_cm']
        
        # Usar dimensiones de caja si existen (para envío)
        if product_dimensions['peso_caja_kg'] > 0:
            peso_kg = product_dimensions['peso_caja_kg']
            largo_cm = product_dimensions['largo_caja_cm'] if product_dimensions['largo_caja_cm'] > 0 else largo_cm
            ancho_cm = product_dimensions['ancho_caja_cm'] if product_dimensions['ancho_caja_cm'] > 0 else ancho_cm
            profundidad_cm = product_dimensions['profundidad_caja_cm'] if product_dimensions['profundidad_caja_cm'] > 0 else profundidad_cm
    else:
        peso_kg = peso_manual
        largo_cm = largo_manual
        ancho_cm = ancho_manual
        profundidad_cm = profundidad_manual
    
    # Mostrar resumen de envío calculado
    if peso_kg > 0 and largo_cm > 0 and ancho_cm > 0 and profundidad_cm > 0:
        billable_weight = get_billable_weight(peso_kg, largo_cm, ancho_cm, profundidad_cm)
        
        st.markdown("---")
        st.markdown("#### 📦 Costo de Envío Calculado")
        
        env_col1, env_col2 = st.columns(2)
        with env_col1:
            # Preview de costo ML (usando precio estimado de $200)
            ml_preview = get_ml_shipping_cost(200, peso_kg, largo_cm, ancho_cm, profundidad_cm)
            st.markdown(f"""
            <div class="fee-breakdown">
                <b>🟡 Mercado Libre (est. $200):</b> ${ml_preview:.2f} MXN<br>
                <b>Peso facturable:</b> {billable_weight:.2f} kg<br>
                <b>Peso volumétrico:</b> {calculate_volumetric_weight(largo_cm, ancho_cm, profundidad_cm):.2f} kg
            </div>
            """, unsafe_allow_html=True)
        
        with env_col2:
            if use_fba:
                fba_preview = get_amazon_fba_fee(peso_kg, largo_cm, ancho_cm, profundidad_cm)
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>🟠 Amazon FBA:</b> ${fba_preview:.2f} MXN<br>
                    <b>Peso facturable:</b> {billable_weight:.2f} kg<br>
                    <b>Tier:</b> {get_amazon_size_tier(largo_cm, ancho_cm, profundidad_cm, peso_kg)}
                </div>
                """, unsafe_allow_html=True)
            else:
                fbm_preview = get_amazon_fbm_shipping(peso_kg, largo_cm, ancho_cm, profundidad_cm)
                st.markdown(f"""
                <div class="fee-breakdown">
                    <b>🟠 Amazon FBM:</b> ${fbm_preview:.2f} MXN<br>
                    <b>Peso facturable:</b> {billable_weight:.2f} kg
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ========== MERCADO LIBRE ==========
    st.markdown("### 🟡 Mercado Libre — Precio Tope + Simulación de Descuentos")
    
    # Calcular precio base tope para 5% ganancia con 60% OFF
    ml_base_price, ml_discounted_60 = calculate_ml_base_price(
        cost, 0.05, 0.60, ml_category, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, peso_kg, largo_cm, ancho_cm, profundidad_cm
    )
    
    # Simular ganancias desde ese precio base fijo con diferentes descuentos
    ml_discount_levels = [0.60, 0.50, 0.40, 0.30]
    ml_scenarios = []
    
    for d in ml_discount_levels:
        scenario = calculate_ml_from_fixed_base(
            cost, ml_base_price, d, ml_category, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, peso_kg, largo_cm, ancho_cm, profundidad_cm
        )
        ml_scenarios.append(scenario)
    
    # Mostrar precio base tope
    st.markdown("#### ⭐ Precio Base Tope (para 5% ganancia con 60% OFF)")
    
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'''
            <div class="metric-card-gold">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Tope ML</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${ml_base_price:,.2f} MXN</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Con 60% OFF → 5% ganancia</div>
            </div>
        ''', unsafe_allow_html=True)
    with m2:
        st.markdown(f'''
            <div class="metric-card-blue">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio con 60% OFF</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${ml_discounted_60:,.2f} MXN</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Lo que paga el cliente</div>
            </div>
        ''', unsafe_allow_html=True)
    with m3:
        profit_60 = ml_scenarios[0]["profit"]
        st.markdown(f'''
            <div class="metric-card-green">
                <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia con 60% OFF</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${profit_60:,.2f}</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Margen: 5.0% (fijo)</div>
            </div>
        ''', unsafe_allow_html=True)
    
    # Tabla comparativa de escenarios
    st.markdown("#### 🏷️ Simulación de Ganancias desde Precio Base Tope")
    
    df_ml = pd.DataFrame([
        {
            "Descuento": f"{s['discount_pct']:.0f}%",
            "Precio Base (Fijo)": f"${s['base_price']:,.2f}",
            "Precio con Descuento": f"${s['discounted_price']:,.2f}",
            "Monto Descuento": f"${s['discount_amount']:,.2f}",
            "Comisiones ML": f"${s['fees']['total_fees']:,.2f}",
            "Ganancia Neta": f"${s['profit']:,.2f}",
            "Margen Real": f"{s['margin']:.1f}%",
            "ROI": f"{s['roi']:.1f}%",
        }
        for s in ml_scenarios
    ])
    
    st.dataframe(df_ml, use_container_width=True, hide_index=True)
    
    # Cards de cada escenario
    st.markdown("#### 📊 Detalle por Nivel de Descuento")
    
    cols = st.columns(4)
    for i, s in enumerate(ml_scenarios):
        with cols[i]:
            # Destacar el de 60% como el tope
            is_best = s['discount_pct'] == 60
            card_class = "scenario-card best" if is_best else "scenario-card"
            
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            
            if is_best:
                st.markdown("🎯 **PRECIO TOPE**")
            
            st.markdown(f"### {s['discount_pct']:.0f}% OFF")
            st.markdown(f"**Precio final:** ${s['discounted_price']:,.2f}")
            st.markdown(f"**Publicidad (10%):** ${s['ad_cost']:,.2f}")
            st.markdown(f"**Ganancia:** ${s['profit']:,.2f}")
            st.markdown(f"**Margen:** {s['margin']:.1f}%")
            
            if s['profit'] < 0:
                st.markdown("<span class='profit-negative'>❌ PÉRDIDA</span>", unsafe_allow_html=True)
            elif s['margin'] < 5:
                st.markdown("<span class='profit-negative'>⚠️ Margen bajo</span>", unsafe_allow_html=True)
            elif s['margin'] >= 20:
                st.markdown("<span class='profit-positive'>✅ Excelente margen</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='profit-positive'>✅ Rentable</span>", unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Fee breakdown
    with st.expander("📋 Desglose completo de costos (al precio con descuento)"):
        s = ml_scenarios[0]  # 60% OFF
        
        st.markdown("#### 💰 Costos del Producto")
        st.markdown(f"""
        <div class="fee-breakdown">
            <b>Costo del producto:</b> ${cost:,.2f}<br>
            <b>Publicidad ({ad_cost_pct*100:.0f}% del precio de venta):</b> ${s['ad_cost']:,.2f}<br>
            <b>Costo total del producto:</b> ${s['total_cost']:,.2f}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### 📦 Comisiones de Mercado Libre")
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
                <b>Envío (por peso):</b> ${s['shipping_cost']:,.2f}<br>
                <b><b>Total comisiones ML:</b></b> ${s['fees']['total_fees']:,.2f} + Envío ${s['shipping_cost']:,.2f}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("#### 🧮 Fórmula de Ganancia")
        st.markdown(f"""
        <div class="fee-breakdown">
            <b>Precio con descuento:</b> ${s['discounted_price']:,.2f}<br>
            <b>− Costo total (producto + publicidad + envío):</b> ${s['total_cost']:,.2f}<br>
            <b>− Comisiones ML + Envío:</b> ${s['fees']['total_fees'] + s['shipping_cost']:,.2f}<br>
            <b>= Ganancia neta:</b> ${s['profit']:,.2f} ({s['margin']:.1f}% margen)
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ========== AMAZON ==========
    st.markdown("### 🟠 Amazon México — Precio Tope + Simulación de Descuentos")
    
    az_fba = fba_cost_per_unit if use_fba else 0
    az_ship = 0 if use_fba else amazon_shipping
    
    # Calcular precio base tope para 5% ganancia con 60% OFF
    az_base_price, az_discounted_60 = calculate_amazon_base_price(
        cost, 0.05, 0.60, az_category, az_fba, az_ship, plan_professional, 0.10, peso_kg, largo_cm, ancho_cm, profundidad_cm, use_fba
    )
    
    # Simular ganancias desde ese precio base fijo
    az_scenarios = []
    for d in [0.60, 0.50, 0.40, 0.30]:
        scenario = calculate_amazon_from_fixed_base(
            cost, az_base_price, d, az_category, az_fba, az_ship, plan_professional, 0.10, peso_kg, largo_cm, ancho_cm, profundidad_cm, use_fba
        )
        az_scenarios.append(scenario)
    
    # Mostrar precio base tope
    st.markdown("#### ⭐ Precio Base Tope (para 5% ganancia con 60% OFF)")
    
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown(f'''
            <div class="metric-card-gold">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Tope Amazon</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${az_base_price:,.2f} MXN</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Con 60% OFF → 5% ganancia</div>
            </div>
        ''', unsafe_allow_html=True)
    with a2:
        st.markdown(f'''
            <div class="metric-card-blue">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio con 60% OFF</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${az_discounted_60:,.2f} MXN</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Lo que paga el cliente</div>
            </div>
        ''', unsafe_allow_html=True)
    with a3:
        az_profit_60 = az_scenarios[0]["profit"]
        st.markdown(f'''
            <div class="metric-card-green">
                <div style="font-size: 0.9rem; opacity: 0.9;">Ganancia con 60% OFF</div>
                <div style="font-size: 2.2rem; font-weight: 700;">${az_profit_60:,.2f}</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Margen: 5.0% (fijo)</div>
            </div>
        ''', unsafe_allow_html=True)
    
    # Tabla comparativa
    df_az = pd.DataFrame([
        {
            "Descuento": f"{s['discount_pct']:.0f}%",
            "Precio Base (Fijo)": f"${s['base_price']:,.2f}",
            "Precio con Descuento": f"${s['discounted_price']:,.2f}",
            "Costo Producto": f"${s['product_cost']:,.2f}",
            "Publicidad (10%)": f"${s['ad_cost']:,.2f}",
            "Comisiones Amazon": f"${s['fees']['total_fees']:,.2f}",
            "Ganancia Neta": f"${s['profit']:,.2f}",
            "Margen Real": f"{s['margin']:.1f}%",
            "ROI": f"{s['roi']:.1f}%",
        }
        for s in az_scenarios
    ])
    
    st.dataframe(df_az, use_container_width=True, hide_index=True)
    
    # Cards de cada escenario
    st.markdown("#### 📊 Detalle por Nivel de Descuento")
    
    cols = st.columns(4)
    for i, s in enumerate(az_scenarios):
        with cols[i]:
            is_best = s['discount_pct'] == 60
            card_class = "scenario-card best" if is_best else "scenario-card"
            
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            
            if is_best:
                st.markdown("🎯 **PRECIO TOPE**")
            
            st.markdown(f"### {s['discount_pct']:.0f}% OFF")
            st.markdown(f"**Precio final:** ${s['discounted_price']:,.2f}")
            st.markdown(f"**Publicidad (10%):** ${s['ad_cost']:,.2f}")
            st.markdown(f"**Ganancia:** ${s['profit']:,.2f}")
            st.markdown(f"**Margen:** {s['margin']:.1f}%")
            
            if s['profit'] < 0:
                st.markdown("<span class='profit-negative'>❌ PÉRDIDA</span>", unsafe_allow_html=True)
            elif s['margin'] < 5:
                st.markdown("<span class='profit-negative'>⚠️ Margen bajo</span>", unsafe_allow_html=True)
            elif s['margin'] >= 20:
                st.markdown("<span class='profit-positive'>✅ Excelente margen</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='profit-positive'>✅ Rentable</span>", unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    with st.expander("📋 Desglose completo de costos (al precio con descuento)"):
        s = az_scenarios[0]
        
        st.markdown("#### 💰 Costos del Producto")
        st.markdown(f"""
        <div class="fee-breakdown">
            <b>Costo del producto:</b> ${cost:,.2f}<br>
            <b>Publicidad ({ad_cost_pct*100:.0f}% del precio de venta):</b> ${s['ad_cost']:,.2f}<br>
            <b>Costo total del producto:</b> ${s['total_cost']:,.2f}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### 📦 Comisiones de Amazon")
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
                <b>FBA (calculado por peso):</b> ${s['fba_cost']:,.2f}<br>
                <b>Envío (calculado por peso):</b> ${s['shipping_cost']:,.2f}<br>
                <b>Total comisiones Amazon:</b> ${s['fees']['total_fees']:,.2f} ({(s['fees']['total_fees']/s['discounted_price'])*100:.1f}%)
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("#### 🧮 Fórmula de Ganancia")
        st.markdown(f"""
        <div class="fee-breakdown">
            <b>Precio con descuento:</b> ${s['discounted_price']:,.2f}<br>
            <b>− Costo total (producto + publicidad + envío):</b> ${s['total_cost']:,.2f}<br>
            <b>− Comisiones Amazon + Envío:</b> ${s['fees']['total_fees'] + s['shipping_cost']:,.2f}<br>
            <b>= Ganancia neta:</b> ${s['profit']:,.2f} ({s['margin']:.1f}% margen)
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# TAB 2: COMPARADOR
# ============================================================
with tab2:
    st.markdown("### 📊 Comparador ML vs Amazon — Mismo Producto")
    st.markdown("Compara el precio base tope y las ganancias en ambos marketplaces desde el mismo costo.")
    
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    
    with comp_col1:
        comp_cost = st.number_input("💵 Costo (MXN)", value=150.0, min_value=0.0, step=10.0, key="comp_cost")
    
    with comp_col2:
        comp_ml_cat = st.selectbox("Categoría ML", list(ML_CATEGORIES.keys()), key="comp_ml_cat")
    
    with comp_col3:
        comp_az_cat = st.selectbox("Categoría Amazon", list(AMAZON_CATEGORIES.keys()), key="comp_az_cat")
    
    # Usar peso y dimensiones del producto seleccionado o manuales
    comp_peso_kg = peso_kg
    comp_largo_cm = largo_cm
    comp_ancho_cm = ancho_cm
    comp_profundidad_cm = profundidad_cm
    
    comp_az_fba = fba_cost_per_unit if use_fba else 0
    comp_az_ship = 0 if use_fba else amazon_shipping
    
    # Calcular precios base tope para ambos
    comp_ml_base, comp_ml_60 = calculate_ml_base_price(
        comp_cost, 0.05, 0.60, comp_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, comp_peso_kg, comp_largo_cm, comp_ancho_cm, comp_profundidad_cm
    )
    comp_az_base, comp_az_60 = calculate_amazon_base_price(
        comp_cost, 0.05, 0.60, comp_az_cat, comp_az_fba, comp_az_ship, plan_professional, 0.10, comp_peso_kg, comp_largo_cm, comp_ancho_cm, comp_profundidad_cm, use_fba
    )
    
    # Simular todos los descuentos
    comp_ml_scenarios = []
    comp_az_scenarios = []
    for d in [0.60, 0.50, 0.40, 0.30]:
        comp_ml_scenarios.append(calculate_ml_from_fixed_base(comp_cost, comp_ml_base, d, comp_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, comp_peso_kg, comp_largo_cm, comp_ancho_cm, comp_profundidad_cm))
        comp_az_scenarios.append(calculate_amazon_from_fixed_base(comp_cost, comp_az_base, d, comp_az_cat, comp_az_fba, comp_az_ship, plan_professional, 0.10, comp_peso_kg, comp_largo_cm, comp_ancho_cm, comp_profundidad_cm, use_fba))
    
    st.markdown("---")
    
    # Precios base tope
    st.markdown("#### ⭐ Precios Base Tope (5% ganancia con 60% OFF)")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🟡 Mercado Libre")
        st.markdown(f'''
            <div class="metric-card">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Tope</div>
                <div style="font-size: 2rem; font-weight: 700;">${comp_ml_base:,.2f} MXN</div>
            </div>
        ''', unsafe_allow_html=True)
        
        for s in comp_ml_scenarios:
            st.markdown(f"""
            - **{s['discount_pct']:.0f}% OFF:** ${s['discounted_price']:,.2f} → Ganancia: ${s['profit']:,.2f} ({s['margin']:.1f}%)
            """)
    
    with c2:
        st.markdown("#### 🟠 Amazon")
        st.markdown(f'''
            <div class="metric-card-orange">
                <div style="font-size: 0.9rem; opacity: 0.9;">Precio Base Tope</div>
                <div style="font-size: 2rem; font-weight: 700;">${comp_az_base:,.2f} MXN</div>
            </div>
        ''', unsafe_allow_html=True)
        
        for s in comp_az_scenarios:
            st.markdown(f"""
            - **{s['discount_pct']:.0f}% OFF:** ${s['discounted_price']:,.2f} → Ganancia: ${s['profit']:,.2f} ({s['margin']:.1f}%)
            """)
    
    # Comparación tabla
    st.markdown("---")
    st.markdown("#### 📋 Tabla Comparativa")
    
    comp_data = []
    for i in range(4):
        ml_s = comp_ml_scenarios[i]
        az_s = comp_az_scenarios[i]
        comp_data.append({
            "Descuento": f"{ml_s['discount_pct']:.0f}%",
            "ML Precio Final": f"${ml_s['discounted_price']:,.2f}",
            "ML Ganancia": f"${ml_s['profit']:,.2f}",
            "ML Margen": f"{ml_s['margin']:.1f}%",
            "AZ Precio Final": f"${az_s['discounted_price']:,.2f}",
            "AZ Ganancia": f"${az_s['profit']:,.2f}",
            "AZ Margen": f"{az_s['margin']:.1f}%",
            "Diferencia": f"${ml_s['profit'] - az_s['profit']:,.2f}",
        })
    
    df_comp = pd.DataFrame(comp_data)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
    
    # Recomendación
    ml_total = sum(s['profit'] for s in comp_ml_scenarios)
    az_total = sum(s['profit'] for s in comp_az_scenarios)
    
    if ml_total > az_total:
        st.success(f"💡 **Mercado Libre genera ${ml_total - az_total:,.2f} más de ganancia** acumulada en los 4 escenarios.")
    else:
        st.success(f"💡 **Amazon genera ${az_total - ml_total:,.2f} más de ganancia** acumulada en los 4 escenarios.")

# ============================================================
# TAB 3: SHOPIFY SYNC
# ============================================================
with tab3:
    st.markdown("### 🔄 Sincronizar con Shopify — morekashop1")
    st.markdown("Carga productos de morekashop1 y calcula precio base tope para 5% ganancia con 60% OFF, luego simula 60%, 50%, 40%, 30% OFF.")
    
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
                st.markdown("#### 📋 Configuración para cálculo masivo")
                
                bulk_ml_cat = st.selectbox("Categoría ML por defecto", list(ML_CATEGORIES.keys()), key="bulk_ml_cat")
                bulk_az_cat = st.selectbox("Categoría Amazon por defecto", list(AMAZON_CATEGORIES.keys()), key="bulk_az_cat")
                
                if st.button("🚀 Calcular Precios Tope para Todos", type="primary"):
                    with st.spinner("Calculando precios tope..."):
                        results = []
                        
                        for _, row in df_with_cost.iterrows():
                            costo = float(row["Costo"])
                            sku = row["SKU"]
                            titulo = row["Título"]
                            
                            # Buscar pesos y medidas por SKU
                            prod_dims = get_product_dimensions(sku, None, pesos_medidas_data) if pesos_medidas_data else None
                            
                            if prod_dims:
                                p_kg = prod_dims['peso_kg']
                                l_cm = prod_dims['largo_cm']
                                a_cm = prod_dims['ancho_cm']
                                pr_cm = prod_dims['profundidad_cm']
                                
                                # Usar dimensiones de caja si existen
                                if prod_dims['peso_caja_kg'] > 0:
                                    p_kg = prod_dims['peso_caja_kg']
                                    l_cm = prod_dims['largo_caja_cm'] if prod_dims['largo_caja_cm'] > 0 else l_cm
                                    a_cm = prod_dims['ancho_caja_cm'] if prod_dims['ancho_caja_cm'] > 0 else a_cm
                                    pr_cm = prod_dims['profundidad_caja_cm'] if prod_dims['profundidad_caja_cm'] > 0 else pr_cm
                            else:
                                p_kg = 0
                                l_cm = 0
                                a_cm = 0
                                pr_cm = 0
                            
                            # ML - Precio base tope para 5% con 60% OFF
                            ml_base, _ = calculate_ml_base_price(
                                costo, 0.05, 0.60, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, p_kg, l_cm, a_cm, pr_cm
                            )
                            
                            # Simular descuentos desde ese precio base
                            ml_60 = calculate_ml_from_fixed_base(costo, ml_base, 0.60, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, p_kg, l_cm, a_cm, pr_cm)
                            ml_50 = calculate_ml_from_fixed_base(costo, ml_base, 0.50, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, p_kg, l_cm, a_cm, pr_cm)
                            ml_40 = calculate_ml_from_fixed_base(costo, ml_base, 0.40, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, p_kg, l_cm, a_cm, pr_cm)
                            ml_30 = calculate_ml_from_fixed_base(costo, ml_base, 0.30, bulk_ml_cat, ml_listing_type, has_rfc, ml_shipping_cost, 0.10, p_kg, l_cm, a_cm, pr_cm)
                            
                            # Amazon - Precio base tope para 5% con 60% OFF
                            az_fba = fba_cost_per_unit if use_fba else 0
                            az_ship = 0 if use_fba else amazon_shipping
                            az_base, _ = calculate_amazon_base_price(
                                costo, 0.05, 0.60, bulk_az_cat, az_fba, az_ship, plan_professional, 0.10, p_kg, l_cm, a_cm, pr_cm, use_fba
                            )
                            
                            az_60 = calculate_amazon_from_fixed_base(costo, az_base, 0.60, bulk_az_cat, az_fba, az_ship, plan_professional, 0.10, p_kg, l_cm, a_cm, pr_cm, use_fba)
                            az_50 = calculate_amazon_from_fixed_base(costo, az_base, 0.50, bulk_az_cat, az_fba, az_ship, plan_professional, 0.10, p_kg, l_cm, a_cm, pr_cm, use_fba)
                            az_40 = calculate_amazon_from_fixed_base(costo, az_base, 0.40, bulk_az_cat, az_fba, az_ship, plan_professional, 0.10, p_kg, l_cm, a_cm, pr_cm, use_fba)
                            az_30 = calculate_amazon_from_fixed_base(costo, az_base, 0.30, bulk_az_cat, az_fba, az_ship, plan_professional, 0.10, p_kg, l_cm, a_cm, pr_cm, use_fba)
                            
                            result_row = {
                                "SKU": sku,
                                "Producto": titulo,
                                "Costo": costo,
                                "Peso kg": round(p_kg, 2) if p_kg > 0 else "—",
                                "Dimensiones": f"{l_cm:.1f}×{a_cm:.1f}×{pr_cm:.1f}" if all([l_cm, a_cm, pr_cm]) else "—",
                                "ML Base Tope": round(ml_base, 2),
                                "ML 60% OFF": round(ml_60['discounted_price'], 2),
                                "ML 60% Ganancia": round(ml_60['profit'], 2),
                                "ML 50% OFF": round(ml_50['discounted_price'], 2),
                                "ML 50% Ganancia": round(ml_50['profit'], 2),
                                "ML 40% OFF": round(ml_40['discounted_price'], 2),
                                "ML 40% Ganancia": round(ml_40['profit'], 2),
                                "ML 30% OFF": round(ml_30['discounted_price'], 2),
                                "ML 30% Ganancia": round(ml_30['profit'], 2),
                                "AZ Base Tope": round(az_base, 2),
                                "AZ 60% OFF": round(az_60['discounted_price'], 2),
                                "AZ 60% Ganancia": round(az_60['profit'], 2),
                                "AZ 50% OFF": round(az_50['discounted_price'], 2),
                                "AZ 50% Ganancia": round(az_50['profit'], 2),
                                "AZ 40% OFF": round(az_40['discounted_price'], 2),
                                "AZ 40% Ganancia": round(az_40['profit'], 2),
                                "AZ 30% OFF": round(az_30['discounted_price'], 2),
                                "AZ 30% Ganancia": round(az_30['profit'], 2),
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
                            f"precios_tope_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv"
                        )
                        
                        try:
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df_results.to_excel(writer, index=False, sheet_name='Precios_Tope')
                            st.download_button(
                                "📥 Descargar Excel",
                                excel_buffer.getvalue(),
                                f"precios_tope_marketplace_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
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
    f"Marketplace Pricing Calculator México 2026 • Precio base tope = 5% ganancia con 60% OFF + 10% publicidad • Comisiones actualizadas: Junio 2026"
    f"</div>",
    unsafe_allow_html=True
)
