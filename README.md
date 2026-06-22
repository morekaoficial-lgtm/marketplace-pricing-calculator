# Marketplace Pricing Calculator

Calculadora de precios para **Mercado Libre** y **Amazon** con comisiones, envíos y descuentos.

## 🚀 Deploy en Streamlit Cloud

1. Sube este repo a GitHub
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repo
4. ¡Listo!

## 📊 Funciones

### 🧮 Calculadora Manual
- Ingresa costo y margen deseado
- Calcula precio óptimo para ML y Amazon
- Evalúa descuentos (5%, 10%, 20%, 30%...)
- Desglose completo de comisiones

### 📊 Comparador de Marketplaces
- Compara el mismo producto en ML vs Amazon
- Ve cuál es más rentable
- Compara precios con descuentos

### 📁 Importar Productos (CSV/Excel)
- Sube un archivo con tus productos
- Calcula precios para todos a la vez
- Exporta resultados a CSV o Excel

## 💰 Comisiones Incluidas

### Mercado Libre
- Comisión por categoría (13-20%)
- Mercado Pago (1.99%)
- IVA sobre comisiones (16%)
- Envío (configurable: gratis o comprador paga)

### Amazon
- Referral Fee (8-15% por categoría)
- Closing Fee (fija)
- FBA (configurable)
- Envío (FBM configurable)

## ⚙️ Configuración

La configuración de envío, FBA y moneda está en la **sidebar** (barra lateral).

## 📁 Estructura

```
marketplace-pricing-calculator/
├── app.py              # App principal
├── requirements.txt    # Dependencias
├── README.md           # Este archivo
└── .gitignore
```

## 📝 Formato CSV para importar

| Columna | Requerido | Descripción |
|---------|-----------|-------------|
| sku | ✅ | Código del producto |
| nombre | ✅ | Nombre del producto |
| costo | ✅ | Costo unitario |
| categoria_ml | ❌ | Categoría ML (usa default si no) |
| categoria_amazon | ❌ | Categoría Amazon (usa default si no) |

## 🛠️ Categorías soportadas

### Mercado Libre
- Electrónica (15%)
- Celulares y Telefonía (13%)
- Computación (14%)
- Audio y Video (15%)
- Accesorios para Vehículos (16%)
- Hogar y Muebles (16%)
- Deportes y Fitness (16%)
- Juegos y Juguetes (16%)
- Custom (configurable)

### Amazon
- Electrónica (8%)
- Celulares y Accesorios (8%)
- Computadoras (8%)
- Audio y Video (8%)
- Instrumentos Musicales (15%)
- Hogar y Cocina (15%)
- Deportes y Aire Libre (15%)
- Juguetes y Juegos (15%)
- Custom (configurable)

---

*Creado el {datetime.now().strftime('%Y-%m-%d')}*
