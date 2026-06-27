#!/usr/bin/env python3
"""
Calculadora de Precios para Marketplaces — México 2026
Mercado Libre y Amazon México con comisiones reales 2026
Lógica: Precio tope calculado para 5% de ganancia con 60% descuento
VERSIÓN: 2026-06-27-v2
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
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# VERSIÓN DEL ARCHIVO (para debug de caché)
# ============================================================
APP_VERSION = "2026-06-27-v3"

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
def get_ml_shipping_cost(price, peso_kg, largo, ancho, profundidad, free_shipping=False):
    """
    Calcula costo de envío de Mercado Libre México — Abril 2026.
    
    REGLAS ACTUALES (desde 6 abril 2026):
    - Productos < $299: El vendedor paga un "costo de servicio de envío" variable por peso,
      AUNQUE el comprador pague el envío en checkout.
    - Productos >= $299: Envío gratis → vendedor paga el costo completo.
    - Si el producto tiene free_shipping=True (aunque sea < $299): vendedor paga tabla "free".
    
    Args:
        price: Precio del producto
        peso_kg, largo, ancho, profundidad: Dimensiones
        free_shipping: True si la publicación tiene envío gratis activado
    
    Returns:
        float: Costo de envío para el VENDEDOR
    """
    billable_weight = get_billable_weight(peso_kg, largo, ancho, profundidad)
    
    if free_shipping:
        # Vendedor ofrece envío gratis → paga tabla completa
        return calculate_ml_shipping_table(billable_weight, price_range="free")
    
    if price >= 299:
        # Producto >= $299 con envío gratis obligatorio
        return calculate_ml_shipping_table(billable_weight, price_range="free")
    
    # Producto < $299: vendedor paga "costo de servicio de envío" (tabla por rango de precio)
    if price < 99:
        price_range = "low"      # $0 - $98.99
    elif price < 199:
        price_range = "mid"      # $99 - $198.99
    else:
        price_range = "high"     # $199 - $298.99
    
    return calculate_ml_shipping_table(billable_weight, price_range)

def calculate_ml_shipping_table(peso_kg, price_range="low"):
    """Tabla de costos de envío ML México — Abril 2026
    
    Fuente: https://www.profitosapp.com/blog/cambios-mercado-envios-full-mexico-abril-2026
    Verificado 7 de abril de 2026 en mercadolibre.com.mx
    
    Desde el 6 de abril 2026:
    - Productos < $299: costo variable por peso según rango de precio (servicio de envío)
    - Productos >= $299 o free_shipping: vendedor paga costo completo (tabla "free")
    """
    
    # Tabla de costos por peso (MXN) — desde 6 de abril 2026
    # Productos menores a $299: costo variable por peso
    shipping_table = {
        "low": {   # $0 - $98.99
            0.3: 25,      # Hasta 0.3 kg
            0.5: 28.50,   # De 0.3 a 0.5 kg
            1.0: 33,      # De 0.5 a 1 kg
            2.0: 35,      # De 1 a 2 kg
            3.0: 37,      # De 2 a 3 kg
            4.0: 39,      # De 3 a 4 kg
            5.0: 40,      # De 4 a 5 kg
            7.0: 45,      # De 5 a 7 kg
            9.0: 51,      # De 7 a 9 kg
            12.0: 59,     # De 9 a 12 kg
            15.0: 69,     # De 12 a 15 kg
            20.0: 81,     # De 15 a 20 kg
            30.0: 102,    # De 20 a 30 kg
            40.0: 126,    # De 30 a 40 kg
            50.0: 163,    # De 40 a 50 kg
            60.0: 183,    # De 50 a 60 kg
        },
        "mid": {   # $99 - $198.99
            0.3: 32,
            0.5: 34,
            1.0: 38,
            2.0: 40,
            3.0: 46,
            4.0: 50,
            5.0: 53,
            7.0: 59,
            9.0: 67,
            12.0: 78,
            15.0: 92,
            20.0: 108,
            30.0: 137,
            40.0: 170,
            50.0: 220,
            60.0: 247,
        },
        "high": {  # $199 - $298.99
            0.3: 35,
            0.5: 38,
            1.0: 39,
            2.0: 41,
            3.0: 48,
            4.0: 54,
            5.0: 59,
            7.0: 70,
            9.0: 81,
            12.0: 96,
            15.0: 113,
            20.0: 140,
            30.0: 195,
            40.0: 250,
            50.0: 305,
            60.0: 334,
        },
        "free": {  # >= $299 (envío gratis — vendedor paga costo real, no mitad)
            # Costo por envío gratis (productos < $299 con envío gratis activado)
            0.3: 52.40,
            0.5: 56,
            1.0: 59.60,
            2.0: 67.60,
            3.0: 76,
            4.0: 82.40,
            5.0: 88,
            7.0: 98,
            9.0: 111.60,
            12.0: 129.20,
            15.0: 152,
            20.0: 178,
            30.0: 225.20,
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

def calculate_ml_base_price(cost, target_margin, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0, ad_cost_pct=0.12, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0, free_shipping=False):
    """Calcula el precio BASE necesario para que el precio con descuento mantenga el margen deseado.
    Incluye costo de publicidad como % del precio de venta y envío basado en peso/dimensiones.
    
    Envío ML México (Abril 2026):
    - Productos < $299: vendedor paga costo de servicio de envío (tabla por peso/rango)
    - Productos >= $299: envío gratis → vendedor paga costo completo
    - free_shipping=True: vendedor paga costo completo sin importar precio
    """
    
    price_discounted = cost * 2.5  # Estimación inicial
    
    for _ in range(30):
        ad_cost = price_discounted * ad_cost_pct
        
        # Calcular envío según reglas actuales
        if peso_kg > 0 or largo_cm > 0 or ancho_cm > 0 or profundidad_cm > 0:
            shipping = get_ml_shipping_cost(price_discounted, peso_kg, largo_cm, ancho_cm, profundidad_cm, free_shipping)
        elif free_shipping or price_discounted >= 299:
            shipping = shipping_cost if shipping_cost > 0 else price_discounted * 0.18
        else:
            # Sin datos de medidas y sin envío gratis: estimar costo de servicio
            shipping = price_discounted * 0.08
        
        total_cost = cost + ad_cost + shipping
        
        fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
        total_fees = fees["total_fees"]
        
        new_price_discounted = (total_cost + total_fees) / (1 - target_margin)
        
        if abs(new_price_discounted - price_discounted) < 0.01:
            break
        price_discounted = new_price_discounted
    
    price_base = price_discounted / (1 - discount_pct)
    
    return round(price_base, 2), round(price_discounted, 2)

def calculate_ml_from_fixed_base(cost, base_price, discount_pct, category_name, listing_type="classic", has_rfc=True, shipping_cost=0, ad_cost_pct=0.12, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0, free_shipping=False):
    """Desde un precio base FIJO, calcula ganancia con un % de descuento dado. Incluye publicidad y envío por peso.
    
    Envío ML México (Abril 2026):
    - Productos < $299: vendedor paga costo de servicio de envío
    - Productos >= $299: envío gratis → vendedor paga costo completo
    """
    price_discounted = base_price * (1 - discount_pct)
    
    ad_cost = price_discounted * ad_cost_pct
    
    # Calcular envío según reglas actuales
    if peso_kg > 0 or largo_cm > 0 or ancho_cm > 0 or profundidad_cm > 0:
        shipping = get_ml_shipping_cost(price_discounted, peso_kg, largo_cm, ancho_cm, profundidad_cm, free_shipping)
    elif free_shipping or price_discounted >= 299:
        shipping = shipping_cost if shipping_cost > 0 else price_discounted * 0.18
    else:
        shipping = price_discounted * 0.08
    
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
# SHOPIFY SYNC — MOREKASHOP1 (con pesos y medidas)
# ============================================================
@st.cache_data(ttl=300)
def fetch_shopify_products():
    """Obtiene productos de morekashop1 con costos, pesos y medidas."""
    try:
        token = st.secrets.get("shopify", {}).get("MOREKA_ACCESS_TOKEN", 
               os.getenv("SHOPIFY_MOREKA_TOKEN", ""))
        if not token:
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
                    return []
                
                data = r.json()
                for product in data.get("products", []):
                    for variant in product.get("variants", []):
                        inv_id = variant.get("inventory_item_id")
                        
                        # Obtener peso y dimensiones del variant
                        weight = variant.get("weight", 0)
                        weight_unit = variant.get("weight_unit", "kg")
                        length = variant.get("length", 0)
                        width = variant.get("width", 0)
                        height = variant.get("height", 0)
                        dimension_unit = variant.get("dimension_unit", "cm")
                        
                        # Convertir peso a kg
                        peso_kg = 0
                        if weight and weight_unit:
                            try:
                                w = float(weight)
                                if weight_unit == "kg":
                                    peso_kg = w
                                elif weight_unit == "g":
                                    peso_kg = w / 1000
                                elif weight_unit == "lb":
                                    peso_kg = w * 0.453592
                                elif weight_unit == "oz":
                                    peso_kg = w * 0.0283495
                            except:
                                pass
                        
                        # Convertir dimensiones a cm
                        largo_cm = 0
                        ancho_cm = 0
                        profundidad_cm = 0
                        if length and dimension_unit:
                            try:
                                l = float(length)
                                if dimension_unit == "cm":
                                    largo_cm = l
                                elif dimension_unit == "in":
                                    largo_cm = l * 2.54
                            except:
                                pass
                        if width and dimension_unit:
                            try:
                                w = float(width)
                                if dimension_unit == "cm":
                                    ancho_cm = w
                                elif dimension_unit == "in":
                                    ancho_cm = w * 2.54
                            except:
                                pass
                        if height and dimension_unit:
                            try:
                                h = float(height)
                                if dimension_unit == "cm":
                                    profundidad_cm = h
                                elif dimension_unit == "in":
                                    profundidad_cm = h * 2.54
                            except:
                                pass
                        
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
                            "Peso kg": round(peso_kg, 3) if peso_kg > 0 else 0,
                            "Largo cm": round(largo_cm, 2) if largo_cm > 0 else 0,
                            "Ancho cm": round(ancho_cm, 2) if ancho_cm > 0 else 0,
                            "Profundidad cm": round(profundidad_cm, 2) if profundidad_cm > 0 else 0,
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
                    pass
            
            for p in products:
                inv_id = p["Inventory Item ID"]
                if inv_id and inv_id in cost_map:
                    p["Costo"] = cost_map[inv_id]
        
        return products
    except Exception as e:
        return []

# ============================================================
# SIDEBAR — CONFIGURACIÓN GLOBAL
# ============================================================
with st.sidebar:
    st.markdown("### 🛒 Producto desde Shopify")
    st.caption(f"v{APP_VERSION}")
    st.markdown("Selecciona un producto para cargar peso, dimensiones y costo automáticamente.")
    
    # Cargar productos desde Shopify
    @st.cache_data(ttl=300)
    def _fetch_shopify_cached():
        return fetch_shopify_products()
    
    shopify_products = _fetch_shopify_cached()
    
    selected_shopify_product = None
    product_dimensions = None
    
    if shopify_products:
        # Only show products with SKU + title, sorted
        products_with_sku = [p for p in shopify_products if p.get("SKU") and p.get("SKU") != "Sin SKU"]
        products_sorted = sorted(products_with_sku, key=lambda x: x.get("Título", "").lower())
        
        # Search box for filtering
        search_term = st.text_input("🔍 Buscar producto", "", key="shopify_search", 
                                     placeholder="Escribe nombre o SKU...")
        
        # Filter products based on search
        if search_term:
            filtered = [p for p in products_sorted if search_term.lower() in p.get("Título", "").lower() or search_term.lower() in p.get("SKU", "").lower()]
        else:
            filtered = products_sorted
        
        if len(filtered) > 0:
            # Create dropdown with limited options if too many
            display_options = []
            product_map = {}
            for p in filtered[:200]:  # Limit to 200 for performance
                display = f"{p.get('SKU', 'N/A')} | {p.get('Título', '')[:50]}"
                display_options.append(display)
                product_map[display] = p
            
            if len(filtered) > 200:
                st.caption(f"Mostrando 200 de {len(filtered)} productos. Escribe para filtrar.")
            else:
                st.caption(f"{len(filtered)} productos encontrados")
            
            selected_display = st.selectbox(
                "Seleccionar producto",
                ["— Elige un producto —"] + display_options,
                index=0,
                key="shopify_select"
            )
            
            if selected_display != "— Elige un producto —":
                selected_shopify_product = product_map[selected_display]
                
                # Create product_dimensions from Shopify
                product_dimensions = {
                    'sku': selected_shopify_product.get('SKU', ''),
                    'modelo': selected_shopify_product.get('Variante', ''),
                    'titulo': selected_shopify_product.get('Título', ''),
                    'peso_kg': selected_shopify_product.get('Peso kg', 0),
                    'largo_cm': selected_shopify_product.get('Largo cm', 0),
                    'ancho_cm': selected_shopify_product.get('Ancho cm', 0),
                    'profundidad_cm': selected_shopify_product.get('Profundidad cm', 0),
                    'peso_caja_kg': 0,
                    'largo_caja_cm': 0,
                    'ancho_caja_cm': 0,
                    'profundidad_caja_cm': 0,
                    'peso_volumetrico': calculate_volumetric_weight(
                        selected_shopify_product.get('Largo cm', 0),
                        selected_shopify_product.get('Ancho cm', 0),
                        selected_shopify_product.get('Profundidad cm', 0)
                    )
                }
                
                # Show product card in sidebar
                st.markdown("---")
                st.markdown("#### 📏 Datos del producto")
                st.markdown(f"""
                <div style='background: #f0fdf4; padding: 12px; border-radius: 8px; border: 1px solid #86efac; font-size: 0.9rem;'>
                    <b>{selected_shopify_product.get('Título', '')}</b><br>
                    <span style='color: #666;'>SKU: {selected_shopify_product.get('SKU', '')}</span><br><br>
                    <b>📦 Peso:</b> {product_dimensions['peso_kg']:.3f} kg<br>
                    <b>📐 Dimensiones:</b> {product_dimensions['largo_cm']:.1f} × {product_dimensions['ancho_cm']:.1f} × {product_dimensions['profundidad_cm']:.1f} cm<br>
                    <b>⚖️ Volumétrico:</b> {product_dimensions['peso_volumetrico']:.3f} kg<br>
                    <b>💵 Costo:</b> ${selected_shopify_product.get('Costo', 0):,.2f} MXN
                </div>
                """, unsafe_allow_html=True)
                
                # Warning if no dimensions
                if product_dimensions['peso_kg'] == 0:
                    st.warning("⚠️ Este producto no tiene peso configurado en Shopify. El envío no se calculará correctamente.")
                if product_dimensions['largo_cm'] == 0 or product_dimensions['ancho_cm'] == 0 or product_dimensions['profundidad_cm'] == 0:
                    st.warning("⚠️ Este producto no tiene dimensiones completas en Shopify. El envío puede ser impreciso.")
        else:
            st.warning("No se encontraron productos con ese término de búsqueda.")
    else:
        st.warning("⚠️ No se pudieron cargar productos de Shopify. Verifica el token en los secrets.")
    
    st.markdown("---")
    st.markdown("### ⚙️ Configuración")
    
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
        "Costo de envío promedio (MXN) — solo si no hay peso",
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
        "Costo FBA por unidad (MXN) — solo si no hay peso",
        value=0.0,
        min_value=0.0,
        step=5.0,
        disabled=not use_fba,
        help="Dejar en 0 para calcular automáticamente por peso y medidas"
    )
    amazon_shipping = st.number_input(
        "Costo de envío FBM por unidad (MXN) — solo si no hay peso",
        value=0.0,
        min_value=0.0,
        step=10.0,
        disabled=use_fba,
        help="Dejar en 0 para calcular automáticamente por peso y medidas"
    )
    
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
# API MERCADO LIBRE — PROMOCIONES Y DESCUENTOS
# ============================================================
MELI_API_BASE = "https://api.mercadolibre.com"

def get_meli_headers(access_token):
    """Headers para requests a API de Mercado Libre"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

@st.cache_data(ttl=300)
def fetch_meli_user_info(access_token):
    """Obtiene información del usuario autenticado en MELI"""
    try:
        r = requests.get(f"{MELI_API_BASE}/users/me", headers=get_meli_headers(access_token), timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": f"HTTP {r.status_code}: {r.text}"}
    except Exception as e:
        return {"error": str(e)}

def map_meli_listing_type(listing_type_id):
    """Mapea listing_type_id de MELI a classic/premium local"""
    if not listing_type_id:
        return "classic"
    # MELI usa: gold_special (Premium), gold_pro (Clásica premium), bronze, free, etc.
    premium_types = ["gold_special", "gold_pro", "gold_premium"]
    if listing_type_id in premium_types:
        return "premium"
    return "classic"

def _fetch_single_item(access_token, item_id):
    """Helper para obtener un item individual (usado en paralelo)"""
    try:
        item_r = requests.get(f"{MELI_API_BASE}/items/{item_id}", headers=get_meli_headers(access_token), timeout=10)
        if item_r.status_code == 200:
            item = item_r.json()
            # SKU: priorizar SELLER_SKU, luego seller_custom_field, luego MODEL/SKU
            sku = ""
            if item.get("attributes"):
                for attr in item.get("attributes", []):
                    if attr.get("id") == "SELLER_SKU":
                        sku = attr.get("value_name", "")
                        break
            if not sku:
                sku = item.get("seller_custom_field", "")
            if not sku and item.get("attributes"):
                for attr in item.get("attributes", []):
                    if attr.get("id") in ["MODEL", "SKU"]:
                        sku = attr.get("value_name", "")
                        break
            # Extraer info de envío desde el objeto shipping de MELI
            shipping_info = item.get("shipping", {})
            free_shipping = shipping_info.get("free_shipping", False)
            shipping_mode = shipping_info.get("mode", "")
            shipping_tags = shipping_info.get("tags", [])
            
            return {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "price": item.get("price", 0),
                "base_price": item.get("base_price", item.get("price", 0)),
                "original_price": item.get("original_price"),
                "available_quantity": item.get("available_quantity", 0),
                "sold_quantity": item.get("sold_quantity", 0),
                "status": item.get("status", ""),
                "permalink": item.get("permalink", ""),
                "thumbnail": item.get("thumbnail", ""),
                "category_id": item.get("category_id", ""),
                "listing_type_id": item.get("listing_type_id", ""),
                "shipping": shipping_info,
                "free_shipping": free_shipping,
                "shipping_mode": shipping_mode,
                "shipping_tags": shipping_tags,
                "sku": sku,
            }
    except:
        pass
    return None

@st.cache_data(ttl=300)
def fetch_meli_items(access_token, user_id, limit=50, offset=0, status="active", fetch_all=True):
    """Obtiene items del seller desde MELI API con paginación automática y requests paralelos"""
    try:
        all_items = []
        current_offset = 0
        max_pages = 20  # Safety limit
        
        while True:
            url = f"{MELI_API_BASE}/users/{user_id}/items/search"
            params = {
                "limit": limit,
                "offset": current_offset,
                "status": status
            }
            r = requests.get(url, headers=get_meli_headers(access_token), params=params, timeout=15)
            if r.status_code != 200:
                return [], f"HTTP {r.status_code}: {r.text}"
            
            data = r.json()
            item_ids = data.get("results", [])
            total = data.get("paging", {}).get("total", 0)
            
            if not item_ids:
                break
            
            # Obtener detalles de cada item EN PARALELO (hasta 20 concurrentes)
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_id = {executor.submit(_fetch_single_item, access_token, item_id): item_id for item_id in item_ids}
                for future in as_completed(future_to_id):
                    item = future.result()
                    if item:
                        all_items.append(item)
            
            # Check if we got all items
            if not fetch_all or len(all_items) >= total or len(item_ids) < limit:
                break
            
            current_offset += limit
            if current_offset >= total or current_offset >= (max_pages * limit):
                break
        
        # Ahora resolver categorías en paralelo (solo las únicas)
        unique_cat_ids = list({item["category_id"] for item in all_items if item.get("category_id")})
        cat_cache = {}
        
        def _fetch_cat(cat_id):
            try:
                r = requests.get(f"{MELI_API_BASE}/categories/{cat_id}", headers=get_meli_headers(access_token), timeout=10)
                if r.status_code == 200:
                    return cat_id, r.json().get("name", "")
            except:
                pass
            return cat_id, ""
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_cat = {executor.submit(_fetch_cat, cat_id): cat_id for cat_id in unique_cat_ids}
            for future in as_completed(future_to_cat):
                cat_id, cat_name = future.result()
                cat_cache[cat_id] = cat_name
        
        # Enriquecer items con categoría y listing_type
        for item in all_items:
            cat_id = item.get("category_id", "")
            meli_cat_name = cat_cache.get(cat_id, "")
            item["meli_category_name"] = meli_cat_name
            item["category_name"] = map_meli_category_to_local(meli_cat_name)
            item["listing_type"] = map_meli_listing_type(item.get("listing_type_id", ""))
        
        return all_items, None
    except Exception as e:
        return [], str(e)

@st.cache_data(ttl=60)
def fetch_meli_item_details(access_token, item_id):
    """Obtiene detalles completos de un item específico"""
    try:
        r = requests.get(f"{MELI_API_BASE}/items/{item_id}", headers=get_meli_headers(access_token), timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

@st.cache_data(ttl=3600)
def get_meli_category_name(access_token, category_id):
    """Obtiene el nombre de una categoría de MELI por su ID"""
    if not category_id:
        return ""
    try:
        r = requests.get(f"{MELI_API_BASE}/categories/{category_id}", headers=get_meli_headers(access_token), timeout=10)
        if r.status_code == 200:
            return r.json().get("name", "")
    except:
        pass
    return ""

def map_meli_category_to_local(meli_category_name):
    """Mapea nombre de categoría de MELI a nuestra categoría local para comisiones"""
    if not meli_category_name:
        return "Custom"
    
    name = meli_category_name.lower()
    
    mappings = {
        "celulares": "Celulares y Telefonía",
        "telefonía": "Celulares y Telefonía",
        "computación": "Computación",
        "electrónica": "Electrónica, Audio y Video",
        "audio": "Electrónica, Audio y Video",
        "video": "Electrónica, Audio y Video",
        "cámaras": "Cámaras y Accesorios",
        "instrumentos": "Instrumentos Musicales",
        "consolas": "Consolas y Videojuegos",
        "videojuegos": "Consolas y Videojuegos",
        "agro": "Agro",
        "alimentos": "Alimentos y Bebidas",
        "bebidas": "Alimentos y Bebidas",
        "accesorios para vehículos": "Accesorios para Vehículos",
        "industrias": "Industrias y Oficinas",
        "herramientas": "Herramientas",
        "belleza": "Belleza y Cuidado Personal",
        "salud": "Salud y Equipamiento Médico",
        "electrodomésticos": "Electrodomésticos",
        "deportes": "Deportes y Fitness",
        "hogar": "Hogar, Muebles y Jardín",
        "juegos": "Juegos y Juguetes",
        "juguetes": "Juegos y Juguetes",
        "joyas": "Joyas y Relojes",
        "relojes": "Joyas y Relojes",
        "libros": "Libros, Revistas y Cómics",
        "mascotas": "Mascotas",
        "ropa": "Ropa, Bolsas y Calzado",
        "bebes": "Bebés",
        "construcción": "Construcción",
        "papelería": "Arte, Papelería y Mercería",
        "mercería": "Arte, Papelería y Mercería",
        "recuerdos": "Recuerdos, Cotillón y Fiestas",
        "cotillón": "Recuerdos, Cotillón y Fiestas",
        "música": "Música, Películas y Series",
        "películas": "Música, Películas y Series",
        "antigüedades": "Antigüedades y Colecciones",
        "colecciones": "Antigüedades y Colecciones",
    }
    
    for key, value in mappings.items():
        if key in name:
            return value
    
    return "Custom"

@st.cache_data(ttl=60)
def fetch_meli_item_prices(access_token, item_id):
    """Obtiene precios y promociones activas de un item (endpoint /items/{id}/prices)"""
    try:
        url = f"{MELI_API_BASE}/items/{item_id}/prices"
        r = requests.get(url, headers=get_meli_headers(access_token), timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

@st.cache_data(ttl=60)
def fetch_meli_promotions(access_token, user_id, status="active"):
    """Obtiene promociones activas del seller — NOTA: endpoint /marketplace/seller-promotions puede no estar disponible"""
    # Este endpoint requiere permisos especiales y a menudo devuelve 403/404
    # Mejor usar fetch_meli_item_prices() por item
    return None

def update_meli_item_price(access_token, item_id, new_price, original_price=None):
    """Actualiza el precio de un item en MELI (solo precio, no promoción oficial)"""
    try:
        url = f"{MELI_API_BASE}/items/{item_id}"
        body = {"price": new_price}
        if original_price and original_price > new_price:
            body["original_price"] = original_price
        r = requests.put(url, headers=get_meli_headers(access_token), json=body, timeout=15)
        if r.status_code in [200, 201]:
            return True, r.json()
        else:
            return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)

def apply_meli_promotion(access_token, item_id, user_id, deal_price, original_price, start_date=None, finish_date=None):
    """
    Aplica una promoción oficial de MELI (PRICE_DISCOUNT).
    Requiere: user_id, deal_price, fechas.
    """
    try:
        url = f"{MELI_API_BASE}/marketplace/seller-promotions/items/{item_id}"
        params = {"user_id": user_id}
        headers = get_meli_headers(access_token)
        headers["version"] = "v2"
        headers["X-Client-Id"] = st.secrets.get("meli", {}).get("app_id", "")
        headers["X-Caller-Id"] = st.secrets.get("meli", {}).get("app_id", "")
        
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if not finish_date:
            finish_date = (datetime.now().replace(day=datetime.now().day + 7)).strftime("%Y-%m-%dT23:59:59")
        
        body = {
            "deal_price": round(deal_price, 2),
            "top_deal_price": round(deal_price * 0.95, 2),
            "start_date": start_date,
            "finish_date": finish_date,
            "promotion_type": "PRICE_DISCOUNT"
        }
        
        r = requests.post(url, headers=headers, params=params, json=body, timeout=15)
        if r.status_code in [200, 201]:
            return True, r.json()
        else:
            return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)


def fetch_item_promotions(access_token, item_id, user_id):
    """
    Obtiene las promociones disponibles para un item específico.
    Endpoint: GET /seller-promotions/items/{item_id}?user_id={user_id}&app_version=v2
    """
    try:
        url = f"{MELI_API_BASE}/seller-promotions/items/{item_id}"
        params = {"user_id": user_id, "app_version": "v2"}
        headers = get_meli_headers(access_token)
        
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()  # Lista de promociones
        elif r.status_code == 400:
            data = r.json()
            if "not allowed" in data.get("message", "").lower():
                return []  # Item no permite promociones
            return {"error": data.get("message", "Error 400")}
        elif r.status_code == 404:
            return []  # No hay promociones para este item
        else:
            return {"error": f"HTTP {r.status_code}: {r.text}"}
    except Exception as e:
        return {"error": str(e)}


def fetch_all_items_promotions(access_token, items, user_id, max_workers=10):
    """
    Obtiene las promociones para todos los items en paralelo.
    Retorna: {item_id: [promociones]}
    """
    results = {}
    
    def _fetch_single(item_id):
        promos = fetch_item_promotions(access_token, item_id, user_id)
        if isinstance(promos, list):
            return item_id, promos
        return item_id, []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_single, item.get("id")): item.get("id") for item in items if item.get("id")}
        for future in as_completed(futures):
            item_id, promos = future.result()
            results[item_id] = promos
    
    return results


def aggregate_unique_promotions(item_promotions_map):
    """
    Agrega promociones únicas a partir del mapa de items.
    Retorna: {promo_id: {info, items: [item_ids]}}
    """
    promos = {}
    
    for item_id, item_promos in item_promotions_map.items():
        for promo in item_promos:
            promo_id = promo.get("id")
            if not promo_id:
                continue
            
            if promo_id not in promos:
                promos[promo_id] = {
                    "id": promo_id,
                    "name": promo.get("name", "Sin nombre"),
                    "type": promo.get("type", "UNKNOWN"),
                    "status": promo.get("status", ""),
                    "start_date": promo.get("start_date", ""),
                    "finish_date": promo.get("finish_date", ""),
                    "items": [],
                    "item_details": [],
                }
            
            promos[promo_id]["items"].append(item_id)
            promos[promo_id]["item_details"].append({
                "item_id": item_id,
                "price": promo.get("price", 0),
                "original_price": promo.get("original_price", 0),
                "meli_percentage": promo.get("meli_percentage", 0),
                "seller_percentage": promo.get("seller_percentage", 0),
                "top_price": promo.get("top_price", 0),
                "min_discounted_price": promo.get("min_discounted_price", 0),
                "max_discounted_price": promo.get("max_discounted_price", 0),
                "suggested_discounted_price": promo.get("suggested_discounted_price", 0),
            })
    
    return promos


def get_promotion_discount_percentage(original_price, promo_price):
    """Calcula el porcentaje de descuento"""
    if original_price <= 0 or promo_price <= 0 or promo_price >= original_price:
        return 0
    return round(((original_price - promo_price) / original_price) * 100, 1)


def enroll_item_to_promotion(access_token, item_id, promo_id, promo_type, deal_price, user_id):
    """
    Inscribe un item en una promoción oficial de MELI.
    
    Endpoints según tipo:
    - DEAL: POST /seller-promotions/items/{item_id}?promotion_type=DEAL&promotion_id={promo_id}&app_version=v2
    - SMART: POST /seller-promotions/items/{item_id}?promotion_type=SMART&promotion_id={promo_id}&app_version=v2
    - PRICE_DISCOUNT: POST /seller-promotions/items/{item_id}?promotion_type=PRICE_DISCOUNT&app_version=v2
    - SELLER_CAMPAIGN: POST /seller-promotions/items/{item_id}?promotion_type=SELLER_CAMPAIGN&promotion_id={promo_id}&app_version=v2
    """
    try:
        url = f"{MELI_API_BASE}/seller-promotions/items/{item_id}"
        
        params = {"app_version": "v2"}
        if promo_type in ["DEAL", "SMART", "SELLER_CAMPAIGN"]:
            params["promotion_type"] = promo_type
            params["promotion_id"] = promo_id
        elif promo_type == "PRICE_DISCOUNT":
            params["promotion_type"] = "PRICE_DISCOUNT"
        else:
            params["promotion_type"] = promo_type
            if promo_id:
                params["promotion_id"] = promo_id
        
        headers = get_meli_headers(access_token)
        
        body = {
            "deal_price": round(deal_price, 2),
            "top_deal_price": round(deal_price * 0.95, 2),
        }
        
        r = requests.post(url, headers=headers, params=params, json=body, timeout=15)
        if r.status_code in [200, 201]:
            return True, r.json()
        else:
            error_msg = parse_meli_promotion_api_error(r.text)
            return False, f"HTTP {r.status_code}: {error_msg}"
    except Exception as e:
        return False, str(e)


def parse_meli_promotion_api_error(response_text):
    """Parsea errores detallados de la API de promociones de MELI"""
    try:
        data = json.loads(response_text)
        msg = data.get("message", "Error desconocido")
        cause = data.get("cause", [])
        if cause:
            details = "; ".join([c.get("message", str(c)) for c in cause])
            return f"{msg} | Detalles: {details}"
        return msg
    except:
        return response_text[:200]

def calculate_meli_net_received(price, fees, shipping_cost, ad_cost_pct=0.12):
    """Calcula el pago neto que MELI muestra: precio - comisiones - envío - publicidad"""
    ad_cost = price * ad_cost_pct
    return price - fees["total_fees"] - shipping_cost - ad_cost

def calculate_meli_promo_discount(cost, current_price, target_margin_pct, category_name, listing_type="classic", has_rfc=True, peso_kg=0, largo_cm=0, ancho_cm=0, profundidad_cm=0, free_shipping=False, ad_cost_pct=0.12):
    """
    Calcula el descuento óptimo para una promoción de MELI con alta precisión.
    
    target_margin_pct: margen deseado sobre el PAGO NETO (ej: 0.05 = 5%)
    free_shipping: True si el producto tiene envío gratis configurado en MELI
    ad_cost_pct: Costo de publicidad como % del precio (default 12%)
    
    Usa método de bisección + refinamiento para convergencia exacta.
    """
    # Helper interno para calcular envío basado en config real del producto
    def _get_shipping_for_price(price):
        if peso_kg > 0 or largo_cm > 0 or ancho_cm > 0 or profundidad_cm > 0:
            return get_ml_shipping_cost(price, peso_kg, largo_cm, ancho_cm, profundidad_cm, free_shipping=free_shipping)
        else:
            # Sin datos de peso/medidas, estimar según rango
            if free_shipping or price >= 299:
                return price * 0.18  # Envío gratis ~18%
            else:
                return price * 0.08  # Costo de servicio ~8%
    # Validaciones básicas
    if cost <= 0 or current_price <= 0:
        return _promo_error(current_price, "Sin costo definido")
    
    # Pago neto objetivo: costo / (1 - margen)
    # Ej: costo=100, margen=5% → necesito recibir $105.26 para ganar 5%
    target_net = cost / (1 - target_margin_pct)
    
    # --- PASO 1: Evaluar precio actual (sin descuento) ---
    fees_actual = calculate_ml_fees(current_price, category_name, listing_type, has_rfc)
    shipping_actual = _get_shipping_for_price(current_price)
    net_actual = calculate_meli_net_received(current_price, fees_actual, shipping_actual, ad_cost_pct)
    profit_actual = net_actual - cost
    margin_actual = (profit_actual / net_actual) * 100 if net_actual > 0 else -999
    
    # Si ya hay pérdida al precio actual
    if profit_actual <= 0:
        return _promo_error(current_price, f"Pérdida actual (${profit_actual:,.2f}). No aplica descuento.", net_actual, profit_actual, margin_actual, fees_actual, shipping_actual, target_net)
    
    # Si el margen actual ya es menor al objetivo
    if margin_actual < (target_margin_pct * 100 - 0.01):  # tolerancia 0.01%
        return _promo_error(current_price, f"Margen actual {margin_actual:.2f}% < {target_margin_pct*100:.0f}% objetivo. No aplica descuento.", net_actual, profit_actual, margin_actual, fees_actual, shipping_actual, target_net)
    
    # --- PASO 2: Buscar precio con descuento usando BISECCIÓN ---
    # Sabemos que: precio=current_price → net >= target_net (ya validamos)
    # Necesitamos encontrar el precio más bajo donde net >= target_net
    # Pero no puede ser menor a costo (obvio)
    
    low = max(cost * 1.05, cost + 10)   # precio mínimo razonable
    high = current_price                # precio máximo = actual
    
    best_price = current_price
    best_margin = margin_actual
    
    for _ in range(60):  # 60 iteraciones = precisión extrema
        mid = (low + high) / 2
        fees_mid = calculate_ml_fees(mid, category_name, listing_type, has_rfc)
        shipping_mid = _get_shipping_for_price(mid)
        net_mid = calculate_meli_net_received(mid, fees_mid, shipping_mid, ad_cost_pct)
        profit_mid = net_mid - cost
        margin_mid = (profit_mid / net_mid) * 100 if net_mid > 0 else -999
        
        # Si el pago neto alcanza el objetivo Y hay ganancia
        if net_mid >= target_net and profit_mid > 0:
            best_price = mid
            best_margin = margin_mid
            high = mid  # Podemos bajar más
        else:
            low = mid   # Necesitamos subir
        
        if abs(high - low) < 0.01:
            break
    
    # --- PASO 3: Refinar con iteración proporcional ---
    price_discounted = best_price
    for _ in range(30):
        fees = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
        shipping = _get_shipping_for_price(price_discounted)
        net_received = calculate_meli_net_received(price_discounted, fees, shipping, ad_cost_pct)
        
        if abs(net_received - target_net) < 0.01:
            break
        
        if net_received > 0 and net_received >= target_net:
            # Podemos bajar un poco más
            adjustment = target_net / net_received
            price_discounted = price_discounted * max(adjustment, 0.999)  # no bajar demasiado rápido
        else:
            # Nos pasamos, subir
            price_discounted = price_discounted * 1.001
    
    # --- PASO 4: Validación final exhaustiva ---
    fees_final = calculate_ml_fees(price_discounted, category_name, listing_type, has_rfc)
    shipping_final = _get_shipping_for_price(price_discounted)
    net_final = calculate_meli_net_received(price_discounted, fees_final, shipping_final, ad_cost_pct)
    profit_final = net_final - cost
    margin_final = (profit_final / net_final) * 100 if net_final > 0 else 0
    
    # Si no hay ganancia o el margen es menor al objetivo, rechazar
    if profit_final <= 0 or margin_final < (target_margin_pct * 100 - 0.05):
        return _promo_error(current_price, f"Margen calculado {margin_final:.2f}% < {target_margin_pct*100:.0f}% objetivo. No aplica.", net_actual, profit_actual, margin_actual, fees_actual, shipping_actual, target_net)
    
    # Si el precio con descuento >= precio actual
    if price_discounted >= current_price * 0.999:
        return _promo_error(current_price, f"Precio actual insuficiente. Necesita ${price_discounted:,.2f} para {target_margin_pct*100:.0f}% margen.", net_actual, profit_actual, margin_actual, fees_actual, shipping_actual, target_net)
    
    # --- PASO 5: Todo OK, calcular descuento ---
    discount_pct = ((current_price - price_discounted) / current_price) * 100
    
    return {
        "price_discounted": round(price_discounted, 2),
        "discount_pct": round(discount_pct, 2),
        "original_price": current_price,
        "net_received": round(net_final, 2),
        "profit": round(profit_final, 2),
        "margin": round(margin_final, 2),
        "fees": fees_final,
        "shipping_cost": round(shipping_final, 2),
        "target_net": round(target_net, 2),
        "aplica": True,
        "mensaje": f"Descuento: {discount_pct:.1f}% | Margen: {margin_final:.2f}%"
    }

def _promo_error(current_price, mensaje, net_actual=0, profit_actual=0, margin_actual=0, fees_actual=None, shipping_actual=0, target_net=0):
    """Helper para retornar estado de error en descuento"""
    return {
        "price_discounted": current_price,
        "discount_pct": 0,
        "original_price": current_price,
        "net_received": round(net_actual, 2),
        "profit": round(profit_actual, 2),
        "margin": round(margin_actual, 2),
        "fees": fees_actual or {"total_fees": 0},
        "shipping_cost": round(shipping_actual, 2),
        "target_net": round(target_net, 2),
        "aplica": False,
        "mensaje": mensaje,
    }

# ============================================================
# TABS PRINCIPALES
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Calculadora Manual",
    "📊 Comparador ML vs Amazon",
    "🔄 Sincronizar Shopify",
    "🎯 Promociones ML"
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
        ad_cost_pct = 0.10
        
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
            
            # Indicar si el envío lo paga el comprador o el vendedor
            if s['discounted_price'] < 299:
                shipping_note = "🟢 Paga el COMPRADOR (precio < $299)"
                shipping_value = "$0.00"
            else:
                shipping_note = "🔴 Envío GRATIS — paga el VENDEDOR"
                shipping_value = f"${s['shipping_cost']:,.2f}"
            
            st.markdown(f"""
            <div class="fee-breakdown">
                <b>IVA retenido ({iva_label}):</b> ${s['fees']['iva_ret']:,.2f}<br>
                <b>ISR retenido ({isr_label}):</b> ${s['fees']['isr_ret']:,.2f}<br>
                <b>Envío:</b> {shipping_value} <span style="font-size: 0.8rem; color: #666;">{shipping_note}</span><br>
                <b><b>Total comisiones ML:</b></b> ${s['fees']['total_fees']:,.2f} + Envío {shipping_value}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("#### 🧮 Fórmula de Ganancia")
        
        # Indicar si envío es costo para vendedor
        if s['discounted_price'] < 299:
            envio_line = f"<b>Envío:</b> $0.00 (paga el comprador, precio < $299)<br>"
        else:
            envio_line = f"<b>Envío:</b> ${s['shipping_cost']:,.2f} (envío gratis, vendedor paga)<br>"
        
        st.markdown(f"""
        <div class="fee-breakdown">
            <b>Precio con descuento:</b> ${s['discounted_price']:,.2f}<br>
            <b>− Costo producto:</b> ${cost:,.2f}<br>
            <b>− Publicidad ({ad_cost_pct*100:.0f}%):</b> ${s['ad_cost']:,.2f}<br>
            {envio_line}
            <b>− Comisiones ML:</b> ${s['fees']['total_fees']:,.2f}<br>
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
        ad_cost_pct = 0.10
        
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
# TAB 4: PROMOCIONES MERCADO LIBRE
# ============================================================
with tab4:
    st.markdown('<div class="main-header">🎯 Promociones Mercado Libre</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Conecta tu cuenta de MELI, arquea costos desde Shopify y calcula descuentos masivos para promociones</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="success-box">
        <b>💡 Cómo funciona:</b> Conecta tu cuenta de Mercado Libre, carga tus publicaciones activas, 
        cruza con costos de Shopify y calcula el <b>descuento óptimo</b> para promociones.
        El margen se calcula sobre el <b>pago neto</b> que indica Mercado Libre (lo que realmente recibes).
    </div>
    """, unsafe_allow_html=True)
    
    # ============================================================
    # SECCIÓN 1: AUTENTICACIÓN MELI
    # ============================================================
    st.markdown("### 🔐 Conexión con Mercado Libre")
    
    # Intentar obtener token desde secrets primero
    meli_token_from_secrets = ""
    try:
        meli_secrets = st.secrets.get("meli", {})
        if meli_secrets:
            meli_token_from_secrets = meli_secrets.get("access_token", "")
    except:
        pass
    
    meli_col1, meli_col2 = st.columns([2, 1])
    
    with meli_col1:
        if meli_token_from_secrets:
            st.success("✅ Token cargado automáticamente desde Secrets")
            meli_token = meli_token_from_secrets
            # Ocultar input si ya hay token en secrets
            show_token_input = st.checkbox("Mostrar token manual", value=False)
            if show_token_input:
                meli_token = st.text_input(
                    "Access Token de Mercado Libre",
                    value=meli_token_from_secrets,
                    type="password",
                    placeholder="APP_USR-XXXXXXXX..."
                )
        else:
            meli_token = st.text_input(
                "Access Token de Mercado Libre",
                value=st.session_state.get("meli_token", ""),
                type="password",
                placeholder="APP_USR-XXXXXXXX...",
                help="Obtén tu token en: https://developers.mercadolibre.com.ar/devcenter"
            )
            if meli_token:
                st.session_state["meli_token"] = meli_token
    
    with meli_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        connect_meli = st.button("🔗 Conectar con MELI", type="primary", use_container_width=True)
    
    # Estado de conexión
    meli_user = None
    meli_items = []
    meli_error = None
    
    if connect_meli and meli_token:
        with st.spinner("Conectando con Mercado Libre..."):
            meli_user = fetch_meli_user_info(meli_token)
            if "error" in meli_user:
                meli_error = meli_user["error"]
                st.error(f"❌ Error de conexión: {meli_error}")
            else:
                user_id = meli_user.get("id")
                user_nickname = meli_user.get("nickname", "")
                st.success(f"✅ Conectado como: **{user_nickname}** (ID: {user_id})")
                
                # Cargar items
                with st.spinner("Cargando publicaciones..."):
                    meli_items, err = fetch_meli_items(meli_token, user_id, status="active")
                    if err:
                        st.warning(f"⚠️ Error cargando items: {err}")
                    else:
                        st.info(f"📦 {len(meli_items)} publicaciones activas cargadas")
    elif meli_token:
        # Reutilizar token de sesión o secrets
        meli_user = fetch_meli_user_info(meli_token)
        if "error" not in meli_user:
            user_id = meli_user.get("id")
            meli_items, _ = fetch_meli_items(meli_token, user_id, status="active")
    
    st.markdown("---")
    
    # ============================================================
    # SECCIÓN 2: CONFIGURACIÓN DE PROMOCIÓN
    # ============================================================
    st.markdown("### ⚙️ Configuración de la Promoción")
    
    config_col1, config_col2, config_col3 = st.columns(3)
    
    with config_col1:
        promo_margin = st.radio(
            "Margen de ganancia deseado",
            ["5% Utilidad", "10% Ganancia"],
            index=0,
            help="5% = margen conservador | 10% = margen agresivo. Calculado sobre el PAGO NETO de MELI."
        )
        target_margin = 0.05 if promo_margin == "5% Utilidad" else 0.10
    
    with config_col2:
        st.markdown("**Tipo de publicación:**")
        st.markdown("<div style='font-size: 0.85rem; color: #666;'>🤖 Detectado automáticamente desde MELI por cada producto</div>", unsafe_allow_html=True)
        st.info("📂 La categoría también se detecta automáticamente desde MELI")
    
    with config_col3:
        promo_has_rfc = st.checkbox("Tengo RFC registrado", value=has_rfc, key="promo_rfc")
        st.markdown("<div style='font-size: 0.8rem; color: #666;'>Afecta IVA/ISR retenido</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    

    # ============================================================
    # SECCIÓN 3: TABLA COMPLETA DE PRODUCTOS CON CÁLCULO DE DESCUENTOS
    # ============================================================
    st.markdown("### 📦 Todos los Productos - Cálculo de Descuentos")
    
    if not meli_items:
        st.warning("⚠️ Primero conecta tu cuenta de Mercado Libre para ver los productos.")
    else:
        # Cargar productos de Shopify para cruzar costos
        shopify_products_for_promo = fetch_shopify_products()
        
        if not shopify_products_for_promo:
            st.warning("⚠️ No se pudieron cargar productos de Shopify. Los costos deberán ingresarse manualmente.")
            shopify_products_for_promo = []
        
        # Crear diccionario de costos por SKU
        shopify_cost_map = {}
        for p in shopify_products_for_promo:
            sku = str(p.get("SKU", "")).strip().upper()
            costo = p.get("Costo")
            if sku and costo is not None:
                shopify_cost_map[sku] = {
                    "costo": costo,
                    "titulo": p.get("Título", ""),
                    "peso_kg": p.get("Peso kg", 0),
                    "largo_cm": p.get("Largo cm", 0),
                    "ancho_cm": p.get("Ancho cm", 0),
                    "profundidad_cm": p.get("Profundidad cm", 0),
                }
        
        # Construir tabla de todos los productos
        todos_productos = []
        for item in meli_items:
            item_sku = str(item.get("sku", "")).strip().upper()
            current_price = item.get("price", 0)
            
            # Buscar costo en Shopify por SKU
            costo_shopify = None
            shopify_info = None
            if item_sku and item_sku in shopify_cost_map:
                shopify_info = shopify_cost_map[item_sku]
                costo_shopify = shopify_info["costo"]
            
            todos_productos.append({
                "meli_id": item.get("id"),
                "title": item.get("title", ""),
                "sku": item.get("sku", ""),
                "current_price": current_price,
                "costo_shopify": costo_shopify,
                "peso_kg": shopify_info["peso_kg"] if shopify_info else 0,
                "largo_cm": shopify_info["largo_cm"] if shopify_info else 0,
                "ancho_cm": shopify_info["ancho_cm"] if shopify_info else 0,
                "profundidad_cm": shopify_info["profundidad_cm"] if shopify_info else 0,
                "stock": item.get("available_quantity", 0),
            })
        
        # ============================================================
        # DEBUG SKU — mostrar coincidencias
        # ============================================================
        with st.expander("🔍 Diagnóstico de SKU (haz clic para ver)"):
            col_dbg1, col_dbg2 = st.columns(2)
            with col_dbg1:
                st.markdown("**Primeros 10 SKU de MELI:**")
                for i, item in enumerate(meli_items[:10]):
                    st.markdown(f"{i+1}. `{item.get('sku') or 'SIN SKU'}` — {item.get('title', '')[:30]}...")
            with col_dbg2:
                st.markdown("**Primeros 10 SKU de Shopify:**")
                shopify_skus = sorted(shopify_cost_map.keys())[:10]
                for sku in shopify_skus:
                    st.markdown(f"• `{sku}` — ${shopify_cost_map[sku]['costo']:,.2f}")
            
            # Contar coincidencias
            coincidencias = sum(1 for item in meli_items if str(item.get("sku", "")).strip().upper() in shopify_cost_map)
            st.info(f"📊 Coincidencias SKU: {coincidencias} de {len(meli_items)} productos MELI tienen costo en Shopify")

        # ============================================================
        # TABLA EDITABLE DE PRODUCTOS
        # ============================================================
        st.markdown("#### ✏️ Tabla de productos con costos (editables)")
        st.info("💡 Los productos con SKU coincidente en Shopify aparecen con costo prellenado. Podés editar cualquier celda.")
        
        # Preparar DataFrame para data_editor
        df_productos = pd.DataFrame([
            {
                "ID MELI": item.get("id"),
                "Producto": item.get("title", ""),
                "SKU MELI": item.get("sku", ""),
                "Tipo Pub": "Premium" if item.get("listing_type") == "premium" else "Clásica",
                "Envío": "Gratis" if item.get("free_shipping") else "Comprador",
                "Precio Base": item.get("price", 0),
                "Costo Shopify": shopify_cost_map.get(str(item.get("sku", "")).strip().upper(), {}).get("costo", 0) or 0,
                "Costo Final": shopify_cost_map.get(str(item.get("sku", "")).strip().upper(), {}).get("costo", 0) or 0,
                "Stock": item.get("available_quantity", 0),
            }
            for item in meli_items
        ])
        
        # Data editor para modificar costos
        edited_df = st.data_editor(
            df_productos,
            column_config={
                "ID MELI": st.column_config.TextColumn("ID MELI", disabled=True),
                "Producto": st.column_config.TextColumn("Producto", disabled=True, width="large"),
                "SKU MELI": st.column_config.TextColumn("SKU MELI", disabled=True),
                "Tipo Pub": st.column_config.TextColumn("Tipo Pub", disabled=True),
                "Envío": st.column_config.TextColumn("Envío", disabled=True),
                "Precio Base": st.column_config.NumberColumn("Precio Base", disabled=True, format="$%.2f"),
                "Costo Shopify": st.column_config.NumberColumn("Costo Shopify", disabled=True, format="$%.2f"),
                "Costo Final": st.column_config.NumberColumn("Costo Final (editable)", min_value=0, step=10.0, format="$%.2f"),
                "Stock": st.column_config.NumberColumn("Stock", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            height=500,
            num_rows="fixed",
        )
        
        # ============================================================
        # BOTÓN CALCULAR
        # ============================================================
        calcular_todos = st.button("🚀 Calcular Descuentos para Todos", type="primary")
        
        if calcular_todos:
            with st.spinner("Calculando descuentos óptimos..."):
                resultados_promo = []
                productos_sin_costo = []  # ← NUEVO: productos sin costo definido
                
                # Diccionario rápido para lookup de items MELI (evita O(n²))
                meli_lookup = {item.get("id"): item for item in meli_items}
                
                for _, row in edited_df.iterrows():
                    costo = row["Costo Final"]
                    current_price = row["Precio Base"]
                    meli_id = row["ID MELI"]
                    sku = row["SKU MELI"]
                    title = row["Producto"]
                    tipo_pub = row["Tipo Pub"]
                    envio_tipo = row["Envío"]
                    stock = row["Stock"]
                    
                    # ── Productos SIN COSTO ──────────────────────────────
                    if costo <= 0:
                        productos_sin_costo.append({
                            "meli_id": meli_id,
                            "sku": sku,
                            "title": title,
                            "current_price": current_price,
                            "tipo_pub": tipo_pub,
                            "envio": envio_tipo,
                            "stock": stock,
                            "costo_sugerido": "",  # columna vacía para que usuario llene
                        })
                        continue
                    
                    # ── Productos CON COSTO ──────────────────────────────
                    # Buscar peso, medidas desde Shopify
                    peso_kg = 0
                    largo_cm = 0
                    ancho_cm = 0
                    profundidad_cm = 0
                    item_sku = str(sku).strip().upper()
                    if item_sku in shopify_cost_map:
                        info = shopify_cost_map[item_sku]
                        peso_kg = info.get("peso_kg", 0)
                        largo_cm = info.get("largo_cm", 0)
                        ancho_cm = info.get("ancho_cm", 0)
                        profundidad_cm = info.get("profundidad_cm", 0)
                    
                    # Obtener categoría, tipo de publicación y envío desde MELI (lookup O(1))
                    meli_item = meli_lookup.get(meli_id, {})
                    item_category = meli_item.get("category_name", "Custom")
                    item_listing_type = meli_item.get("listing_type", "classic")
                    item_free_shipping = meli_item.get("free_shipping", False)
                    
                    # Calcular descuento óptimo
                    resultado = calculate_meli_promo_discount(
                        cost=costo,
                        current_price=current_price,
                        target_margin_pct=target_margin,
                        category_name=item_category,
                        listing_type=item_listing_type,
                        has_rfc=promo_has_rfc,
                        peso_kg=peso_kg,
                        largo_cm=largo_cm,
                        ancho_cm=ancho_cm,
                        profundidad_cm=profundidad_cm,
                        free_shipping=item_free_shipping
                    )
                    
                    resultados_promo.append({
                        "meli_id": meli_id,
                        "sku": sku,
                        "title": title,
                        "current_price": current_price,
                        "costo": costo,
                        "precio_promo": resultado["price_discounted"],
                        "descuento_pct": resultado["discount_pct"],
                        "descuento_monto": round(current_price - resultado["price_discounted"], 2) if current_price > resultado["price_discounted"] else 0,
                        "comisiones": resultado["fees"]["total_fees"],
                        "envio": resultado["shipping_cost"],
                        "pago_neto": resultado["net_received"],
                        "ganancia": resultado["profit"],
                        "margen_sobre_neto": resultado["margin"],
                        "aplicar": resultado.get("aplica", False),
                        "estado": resultado.get("mensaje", "—"),
                    })
                
                # ============================================================
                # MOSTRAR RESULTADOS — SOLO PRODUCTOS CON COSTO
                # ============================================================
                if resultados_promo:
                    st.success(f"✅ {len(resultados_promo)} productos con costo calculados")
                    
                    # Mostrar tabla de resultados (solo con costo)
                    df_resultados = pd.DataFrame([
                        {
                            "ID MELI": r["meli_id"],
                            "SKU": r["sku"] or "—",
                            "Producto": r["title"][:35] + "..." if len(r["title"]) > 35 else r["title"],
                            "Precio Base": f"${r['current_price']:,.2f}",
                            "Costo": f"${r['costo']:,.2f}",
                            "Precio Promo": f"${r['precio_promo']:,.2f}" if r['precio_promo'] > 0 else "—",
                            "Descuento %": f"{r['descuento_pct']:.1f}%" if r['descuento_pct'] > 0 else "—",
                            "Pago Neto": f"${r['pago_neto']:,.2f}" if r['pago_neto'] > 0 else "—",
                            "Ganancia": f"${r['ganancia']:,.2f}" if r['ganancia'] != 0 else "—",
                            "Margen": f"{r['margen_sobre_neto']:.1f}%" if r['margen_sobre_neto'] != 0 else "—",
                            "Estado": r["estado"],
                        }
                        for r in resultados_promo
                    ])
                    
                    st.dataframe(df_resultados, use_container_width=True, hide_index=True, height=600)
                    
                    # ============================================================
                    # EXPORTAR A EXCEL — SOLO CON COSTO
                    # ============================================================
                    st.markdown("### 📥 Exportar a Excel (productos con costo)")
                    
                    try:
                        excel_buffer = BytesIO()
                        df_export = pd.DataFrame(resultados_promo)
                        df_export = df_export[["meli_id", "sku", "title", "current_price", "costo", 
                                               "precio_promo", "descuento_pct", "pago_neto", 
                                               "ganancia", "margen_sobre_neto", "estado"]]
                        # Convertir descuento a entero (35.0 → 35)
                        df_export["descuento_pct"] = df_export["descuento_pct"].fillna(0).astype(int)
                        df_export.columns = ["ID MELI", "SKU", "Producto", "Precio Base", "Costo",
                                             "Precio Promo", "Descuento", "Pago Neto",
                                             "Ganancia", "Margen %", "Estado"]
                        
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df_export.to_excel(writer, sheet_name='Descuentos', index=False)
                        
                        excel_buffer.seek(0)
                        st.download_button(
                            "📊 Descargar Excel (con costo)",
                            excel_buffer.getvalue(),
                            f"promociones_meli_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.warning(f"⚠️ No se pudo generar Excel: {e}")
                        csv_buffer = io.StringIO()
                        df_csv = pd.DataFrame(resultados_promo)
                        df_csv["descuento_pct"] = df_csv["descuento_pct"].fillna(0).astype(int)
                        df_csv.columns = ["ID MELI", "SKU", "Producto", "Precio Base", "Costo",
                                          "Precio Promo", "Descuento", "Pago Neto",
                                          "Ganancia", "Margen %", "Estado"]
                        df_csv.to_csv(csv_buffer, index=False)
                        st.download_button(
                            "📄 Descargar CSV (con costo)",
                            csv_buffer.getvalue(),
                            f"promociones_meli_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv"
                        )
                    
                    # ============================================================
                    # PRODUCTOS SIN COSTO — TABLA + EXCEL SEPARADO
                    # ============================================================
                    if productos_sin_costo:
                        st.markdown("---")
                        st.warning(f"⚠️ {len(productos_sin_costo)} productos SIN COSTO definido")
                        
                        # Mostrar tabla resumen
                        df_sin_costo = pd.DataFrame([
                            {
                                "ID MELI": p["meli_id"],
                                "SKU": p["sku"] or "—",
                                "Producto": p["title"][:40] + "..." if len(p["title"]) > 40 else p["title"],
                                "Precio Base": f"${p['current_price']:,.2f}",
                                "Tipo Pub": p["tipo_pub"],
                                "Envío": p["envio"],
                                "Stock": p["stock"],
                            }
                            for p in productos_sin_costo
                        ])
                        
                        st.dataframe(df_sin_costo, use_container_width=True, hide_index=True, height=min(len(productos_sin_costo)*45, 400))
                        
                        # Exportar Excel de productos sin costo
                        st.markdown("### 📥 Exportar Excel — Productos Sin Costo")
                        st.caption("Incluye columna 'Costo Sugerido' vacía para que completes y reimportes.")
                        
                        try:
                            excel_sc_buffer = BytesIO()
                            df_sc_export = pd.DataFrame(productos_sin_costo)
                            df_sc_export.columns = ["ID MELI", "SKU", "Producto", "Precio Base", 
                                                     "Tipo Pub", "Envío", "Stock", "Costo Sugerido"]
                            
                            with pd.ExcelWriter(excel_sc_buffer, engine='openpyxl') as writer:
                                df_sc_export.to_excel(writer, sheet_name='Sin_Costo', index=False)
                            
                            excel_sc_buffer.seek(0)
                            st.download_button(
                                "📋 Descargar Excel (sin costo)",
                                excel_sc_buffer.getvalue(),
                                f"productos_sin_costo_meli_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except Exception as e:
                            st.warning(f"⚠️ No se pudo generar Excel: {e}")
                    
                    # Guardar en session_state para persistir entre interacciones
                    st.session_state.resultados_promo = resultados_promo
                    st.session_state.productos_sin_costo = productos_sin_costo
                    
                    # ============================================================
                    # PROMOCIONES OFICIALES MELI (guardar en session_state)
                    # ============================================================
                    st.session_state.resultados_promo = resultados_promo
                    st.session_state.productos_sin_costo = productos_sin_costo
                    st.session_state.calculation_done = True


        # ============================================================
        # PROMOCIONES OFICIALES MELI (siempre visible después de calcular)
        # ============================================================
        if st.session_state.get("calculation_done") and meli_token and meli_user:
            st.markdown("---")
            st.markdown("### 🏷️ Promociones Oficiales de Mercado Libre")
            st.caption("Inscribe tus productos en promociones oficiales de MELI (OFERTA DEL DÍA, etc.)")
            
            resultados_promo = st.session_state.get("resultados_promo", [])
            
            with st.spinner("Cargando promociones disponibles..."):
                meli_user_id = meli_user.get("id", "")
                
                try:
                    promociones_por_item = fetch_all_items_promotions(meli_token, meli_items, meli_user_id)
                except NameError as e:
                    st.error(f"❌ Error de carga (caché): {e}")
                    st.info("🔄 Intentá recargar la app con Ctrl+Shift+R o reiniciá desde 'Manage app'")
                    promociones_por_item = {}
                
                if isinstance(promociones_por_item, dict) and "error" in promociones_por_item:
                    st.error(f"❌ Error al cargar promociones: {promociones_por_item['error']}")
                else:
                    unique_promos = aggregate_unique_promotions(promociones_por_item)
                    
                    if not unique_promos:
                        st.info("📭 No hay promociones oficiales disponibles para tus productos en este momento.")
                    else:
                        enrollable_promos = {k: v for k, v in unique_promos.items() if v.get("status") in ["candidate", "pending", ""]}
                        active_promos = {k: v for k, v in unique_promos.items() if v.get("status") == "started"}
                        
                        if active_promos:
                            st.success(f"🎉 {len(active_promos)} promoción(es) ya activa(s) en tus productos")
                            with st.expander("Ver promociones activas"):
                                for promo_id, promo in active_promos.items():
                                    st.markdown(f"**{promo['name']}** ({promo['type']}) — {len(promo['items'])} productos")
                        
                        if not enrollable_promos:
                            st.info("📭 No hay promociones disponibles para inscribir en este momento. Las promociones activas ya están corriendo.")
                        else:
                            st.success(f"🎉 {len(enrollable_promos)} promoción(es) disponible(s) para inscribir")
                            
                            promo_options = {}
                            for promo_id, promo in enrollable_promos.items():
                                label = f"{promo['name']} ({promo['type']}) — {len(promo['items'])} productos"
                                promo_options[label] = promo
                            
                            promo_seleccionada = st.selectbox(
                                "Selecciona una promoción:",
                                options=list(promo_options.keys()),
                                key="promo_selector"
                            )
                            
                            if promo_seleccionada:
                                promo = promo_options[promo_seleccionada]
                                promo_id = promo["id"]
                                promo_type = promo["type"]
                                
                                st.markdown(f"**Tipo:** {promo_type} | **Estado:** {promo['status']}")
                                if promo['start_date'] and promo['finish_date']:
                                    st.caption(f"📅 {promo['start_date'][:10]} → {promo['finish_date'][:10]}")
                                
                                st.markdown("#### ✅ Productos disponibles para inscribir")
                                
                                productos_califican = []
                                for detail in promo["item_details"]:
                                    item_id = detail["item_id"]
                                    r = None
                                    for res in resultados_promo:
                                        if res["meli_id"] == item_id:
                                            r = res
                                            break
                                    
                                    if not r:
                                        continue
                                    
                                    original_price = detail.get("original_price", r["current_price"])
                                    min_price = detail.get("min_discounted_price", 0)
                                    max_price = detail.get("max_discounted_price", original_price)
                                    suggested_price = detail.get("suggested_discounted_price", 0)
                                    
                                    our_price = r["precio_promo"]
                                    discount_pct = get_promotion_discount_percentage(original_price, our_price)
                                    
                                    qualifies = min_price <= our_price <= max_price if min_price > 0 and max_price > 0 else True
                                    
                                    productos_califican.append({
                                        "meli_id": item_id,
                                        "title": r["title"],
                                        "current_price": r["current_price"],
                                        "precio_promo": our_price,
                                        "discount_pct": discount_pct,
                                        "min_price": min_price,
                                        "max_price": max_price,
                                        "suggested_price": suggested_price,
                                        "qualifies": qualifies,
                                        "margen_sobre_neto": r["margen_sobre_neto"],
                                    })
                                
                                if productos_califican:
                                    ok_items = [p for p in productos_califican if p["qualifies"]]
                                    nok_items = [p for p in productos_califican if not p["qualifies"]]
                                    
                                    if ok_items:
                                        st.info(f"{len(ok_items)} productos pueden inscribirse")
                                        
                                        df_calif = pd.DataFrame([
                                            {
                                                "ID MELI": p["meli_id"],
                                                "Producto": p["title"][:35] + "..." if len(p["title"]) > 35 else p["title"],
                                                "Precio Actual": f"${p['current_price']:,.2f}",
                                                "Precio Promo": f"${p['precio_promo']:,.2f}",
                                                "Desc.%": f"{p['discount_pct']:.1f}%",
                                                "Margen": f"{p['margen_sobre_neto']:.1f}%",
                                            }
                                            for p in ok_items
                                        ])
                                        st.dataframe(df_calif, use_container_width=True, hide_index=True, height=min(len(ok_items)*45, 350))
                                        
                                        inscribir_promo = st.button(
                                            f"🏷️ Inscribir {len(ok_items)} productos en '{promo['name']}'",
                                            type="primary",
                                            key="btn_inscribir_promo"
                                        )
                                        
                                        if inscribir_promo:
                                            with st.spinner("Inscribiendo productos..."):
                                                inscritos = 0
                                                errores_promo = []
                                                
                                                def _enroll_single(p):
                                                    deal_price = p["precio_promo"]
                                                    if p["suggested_price"] > 0 and p["suggested_price"] < deal_price:
                                                        deal_price = p["suggested_price"]
                                                    
                                                    success, result = enroll_item_to_promotion(
                                                        meli_token,
                                                        p["meli_id"],
                                                        promo_id,
                                                        promo_type,
                                                        deal_price,
                                                        meli_user_id
                                                    )
                                                    return success, p["meli_id"], result
                                                
                                                with ThreadPoolExecutor(max_workers=10) as executor:
                                                    futures = {executor.submit(_enroll_single, p): p for p in ok_items}
                                                    for future in as_completed(futures):
                                                        success, meli_id, result = future.result()
                                                        if success:
                                                            inscritos += 1
                                                        else:
                                                            errores_promo.append(f"{meli_id}: {result}")
                                                
                                                if inscritos > 0:
                                                    st.success(f"✅ {inscritos}/{len(ok_items)} productos inscritos")
                                                if errores_promo:
                                                    with st.expander(f"❌ Errores ({len(errores_promo)}):"):
                                                        for err in errores_promo[:10]:
                                                            st.markdown(f"• {err}")
                                    else:
                                        st.warning("⚠️ Ningún producto califica con el precio calculado. Verificá los rangos de precios.")
                                    
                                    if nok_items:
                                        with st.expander(f"⚠️ {len(nok_items)} productos fuera de rango"):
                                            st.caption("El precio calculado está fuera del rango permitido por MELI para esta promoción")
                                            df_nok = pd.DataFrame([
                                                {
                                                    "ID MELI": p["meli_id"],
                                                    "Producto": p["title"][:30] + "...",
                                                    "Nuestro Precio": f"${p['precio_promo']:,.2f}",
                                                    "Mínimo": f"${p['min_price']:,.2f}",
                                                    "Máximo": f"${p['max_price']:,.2f}",
                                                }
                                                for p in nok_items[:10]
                                            ])
                                            st.dataframe(df_nok, use_container_width=True, hide_index=True)
                                else:
                                    st.warning("⚠️ No se encontraron productos para esta promoción.")
        
        elif meli_token and meli_user and not st.session_state.get("calculation_done"):
            st.info("🔑 Calculá los descuentos primero para ver las promociones disponibles")
                    
# FOOTER
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
