# Marketplace Pricing Calculator — Quick Reference

## Links
- **Repositorio:** https://github.com/morekaoficial-lgtm/marketplace-pricing-calculator
- **Deploy:** https://share.streamlit.io → Buscar `morekaoficial-lgtm/marketplace-pricing-calculator`
- **Local:** `cd /root/.openclaw/workspace/marketplace-pricing-calculator && streamlit run app.py`

## Cómo usar

### 1. Calculadora Manual (Tab 1)
- Ingresa **costo** y **margen deseado**
- Selecciona **categoría** para ML y Amazon
- La app calcula precio base + desglose de comisiones
- Evalúa descuentos (5%, 10%, 20%, 30%...)
- ⚠️ Alerta si un descuento te hace perder dinero

### 2. Comparador (Tab 2)
- Compara mismo producto en ML vs Amazon
- Te dice cuál es más rentable
- Compara precios con descuentos en ambos

### 3. Importar CSV/Excel (Tab 3)
- Sube archivo con columnas: `sku`, `nombre`, `costo`
- Opcional: `categoria_ml`, `categoria_amazon`
- Calcula todos los productos a la vez
- Exporta a CSV o Excel

## Configuración (Sidebar)
- **Moneda:** MXN / USD / COP / ARS
- **Envío ML:** Gratis o comprador paga
- **Amazon FBA:** Sí/No + costo por unidad

## Comisiones por categoría (ML)
| Categoría | Comisión |
|---|---|
| Electrónica | 15% |
| Celulares | 13% |
| Computación | 14% |
| Audio/Video | 15% |
| Vehículos | 16% |
| Hogar | 16% |
| Deportes | 16% |
| Juguetes | 16% |

## Comisiones por categoría (Amazon)
| Categoría | Referral |
|---|---|
| Electrónica | 8% |
| Celulares | 8% |
| Computadoras | 8% |
| Audio/Video | 8% |
| Instrumentos | 15% |
| Hogar | 15% |
| Deportes | 15% |
| Juguetes | 15% |

## Última actualización: 23 Junio 2026
